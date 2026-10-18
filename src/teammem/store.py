"""Armazenamento: o repositório git é a única fonte da verdade.

Layout local (por acervo, em ~/.teammem/<nome>/):
  main/   clone da branch main  -> memórias validadas/promovidas (somente leitura aqui)
  inbox/  worktree da branch inbox -> propostas pendentes, escritas via `propose`
  index.sqlite  índice FTS5 derivado (descartável)
  .last_sync    marcador de throttle do pull

Leitura nunca espera a rede: se o fetch falhar, serve o que existe localmente.
Escrita: cada proposta é um arquivo novo em inbox/ na branch inbox, então pushes
concorrentes nunca conflitam (no pior caso, `pull --rebase` e nova tentativa).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .config import Config
from .schema import Memory, SchemaError, parse

MEMORY_DIRS = ("global", "team", "org", "project")


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: Path | str | None = None, check: bool = True, timeout: int = 60) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        res = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        raise GitError(f"git {' '.join(args)}: timeout") from e
    except OSError as e:  # cwd inexistente, git ausente
        raise GitError(f"git {' '.join(args)}: {e}") from e
    if check and res.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout.strip()


class Store:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    # ------------------------------------------------------------------ setup
    def ensure(self) -> None:
        """Clona o acervo e prepara o worktree da inbox, se ainda não existirem."""
        cfg = self.cfg
        cfg.base.mkdir(parents=True, exist_ok=True)
        if not (cfg.main_dir / ".git").exists():
            git("clone", "--branch", cfg.main_branch, cfg.repo, str(cfg.main_dir), timeout=300)
        if not (cfg.inbox_dir / ".git").exists():
            self._create_inbox_worktree()

    def _remote_has(self, branch: str) -> bool:
        out = git("ls-remote", "--heads", "origin", branch, cwd=self.cfg.main_dir, check=False)
        return bool(out.strip())

    def _create_inbox_worktree(self) -> None:
        cfg = self.cfg
        git("fetch", "origin", cwd=cfg.main_dir, check=False)
        ib = cfg.inbox_branch
        if self._remote_has(ib):
            git("worktree", "add", "-B", ib, str(cfg.inbox_dir), f"origin/{ib}", cwd=cfg.main_dir)
            git("branch", f"--set-upstream-to=origin/{ib}", ib, cwd=cfg.inbox_dir, check=False)
        else:
            git("worktree", "add", "-B", ib, str(cfg.inbox_dir), f"origin/{cfg.main_branch}",
                cwd=cfg.main_dir)
            (cfg.inbox_dir / "inbox").mkdir(exist_ok=True)
            keep = cfg.inbox_dir / "inbox" / ".gitkeep"
            if not keep.exists():
                keep.write_text("")
                git("add", "inbox/.gitkeep", cwd=cfg.inbox_dir)
                self._commit(cfg.inbox_dir, "inbox: inicializa branch de propostas")
            git("push", "-u", "origin", ib, cwd=cfg.inbox_dir, check=False)

    # ------------------------------------------------------------------- sync
    @property
    def _stamp(self) -> Path:
        return self.cfg.base / ".last_sync"

    def sync(self, force: bool = False) -> dict:
        """Atualiza main e inbox. Falhas de rede não são fatais."""
        self.ensure()
        if not force and self._stamp.exists():
            if time.time() - self._stamp.stat().st_mtime < self.cfg.sync_seconds:
                return {"synced": False, "reason": "throttle"}
        cfg = self.cfg
        result: dict = {"synced": True, "errors": []}
        try:
            git("fetch", "origin", "--prune", cwd=cfg.main_dir)
            git("merge", "--ff-only", f"origin/{cfg.main_branch}", cwd=cfg.main_dir)
        except GitError as e:
            result["errors"].append(f"main: {e}")
        try:
            if self._remote_has(cfg.inbox_branch):
                git("pull", "--rebase", "origin", cfg.inbox_branch, cwd=cfg.inbox_dir)
            pending = self.pending_push()
            if pending:
                git("push", "origin", cfg.inbox_branch, cwd=cfg.inbox_dir)
                result["pushed_pending"] = pending
        except GitError as e:
            result["errors"].append(f"inbox: {e}")
        self._stamp.touch()
        return result

    def pending_push(self) -> int:
        """Commits locais da inbox ainda não enviados (fila offline)."""
        out = git("rev-list", "--count", f"origin/{self.cfg.inbox_branch}..HEAD",
                  cwd=self.cfg.inbox_dir, check=False)
        try:
            return int(out or 0)
        except ValueError:
            return 0

    def head(self, which: str = "main") -> str:
        d = self.cfg.main_dir if which == "main" else self.cfg.inbox_dir
        try:
            return git("rev-parse", "HEAD", cwd=d, check=False)
        except GitError:
            return ""

    # ------------------------------------------------------------------ leitura
    def _load_dir(self, root: Path, subdirs: tuple[str, ...], origin: str) -> list[Memory]:
        mems: list[Memory] = []
        for sub in subdirs:
            base = root / sub
            if not base.exists():
                continue
            for f in sorted(base.rglob("*.md")):
                rel = f.relative_to(root).as_posix()
                try:
                    mems.append(parse(f.read_text(encoding="utf-8"), path=rel, origin=origin))
                except (SchemaError, UnicodeDecodeError):
                    continue  # arquivo inválido não derruba a leitura
        return mems

    def main_memories(self) -> list[Memory]:
        return self._load_dir(self.cfg.main_dir, MEMORY_DIRS, "main")

    def inbox_memories(self) -> list[Memory]:
        return self._load_dir(self.cfg.inbox_dir, ("inbox",), "inbox")

    def all_memories(self) -> list[Memory]:
        main = self.main_memories()
        promoted = {m.id for m in main}
        return main + [m for m in self.inbox_memories() if m.id not in promoted]

    def policy(self) -> dict:
        """Política do acervo (.teammem.yaml na main)."""
        import yaml

        f = self.cfg.main_dir / ".teammem.yaml"
        if f.exists():
            try:
                return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                return {}
        return {}

    # ------------------------------------------------------------------ escrita
    def _commit(self, cwd: Path, msg: str) -> None:
        args = ["commit", "-m", msg]
        if self.cfg.author:
            args = ["-c", f"user.name={self.cfg.author}", *args]
        git(*args, cwd=cwd)

    def propose(self, mem: Memory) -> dict:
        """Grava a proposta na inbox e tenta publicar. Sem rede, fica na fila local."""
        self.ensure()
        cfg = self.cfg
        if self._remote_has(cfg.inbox_branch):
            git("pull", "--rebase", "origin", cfg.inbox_branch, cwd=cfg.inbox_dir, check=False)
        dest = cfg.inbox_dir / mem.inbox_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise FileExistsError(f"já existe uma proposta com id {mem.id}")
        dest.write_text(mem.to_markdown(), encoding="utf-8")
        git("add", mem.inbox_path(), cwd=cfg.inbox_dir)
        self._commit(cfg.inbox_dir, f"memory: propõe {mem.id}")
        for attempt in range(2):
            try:
                git("push", "origin", cfg.inbox_branch, cwd=cfg.inbox_dir)
                return {"status": "publicada", "id": mem.id, "path": mem.inbox_path()}
            except GitError as e:
                last = str(e)
                if attempt == 0:
                    git("pull", "--rebase", "origin", cfg.inbox_branch, cwd=cfg.inbox_dir,
                        check=False)
        return {
            "status": "na_fila",
            "id": mem.id,
            "path": mem.inbox_path(),
            "detalhe": f"push falhou; será reenviada no próximo sync ({last})",
        }
