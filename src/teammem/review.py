"""Revisão e promoção inbox -> main.

Dois modos, mesmo código:
- "pr"     (trabalho): cria branch promote/* a partir da main só com os itens
            aprovados, faz push e abre PR. O merge continua humano.
- "direct" (particular/CI): commit direto na main com status provisional.

A inbox nunca é mergeada inteira: a branch de promoção nasce da main e recebe
só os arquivos escolhidos. Depois do merge, `gc` limpa a inbox.
"""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import curator
from .schema import parse
from .store import GitError, Store, git

TRAILER = "Gerado por teammem review"


def in_flight(store: Store) -> set[str]:
    """Ids que já estão em alguma branch promote/* aguardando merge."""
    d = store.cfg.main_dir
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/promote/",
               cwd=d, check=False).split()
    ids: set[str] = set()
    for ref in refs:
        changed = git("diff", "--name-only", f"origin/{store.cfg.main_branch}...{ref}",
                      cwd=d, check=False).split()
        ids |= {Path(p).stem for p in changed if p.endswith(".md")}
    return ids


def pending(store: Store) -> list[curator.Verdict]:
    main = store.main_memories()
    main_ids = {m.id for m in main}
    skip = main_ids | in_flight(store)
    inbox = [m for m in store.inbox_memories() if m.id not in skip]
    policy = store.policy()
    verdicts = []
    for m in inbox:
        others = main + [o for o in inbox if o.id != m.id and o.created <= m.created]
        verdicts.append(curator.classify(m, others, policy))
    order = {"bloqueado": 0, "humano": 1, "auto": 2}
    return sorted(verdicts, key=lambda v: (order[v.tier], v.memory.created))


def _open_pr(cwd: Path, branch: str, base: str, title: str, body: str) -> str | None:
    if shutil.which("gh"):
        r = subprocess.run(
            ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title,
             "--body", body],
            cwd=cwd, capture_output=True, text=True,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    if shutil.which("glab"):
        r = subprocess.run(
            ["glab", "mr", "create", "--source-branch", branch, "--target-branch", base,
             "--title", title, "--description", body, "--yes"],
            cwd=cwd, capture_output=True, text=True,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    return None


def promote(store: Store, ids: list[str], mode: str = "pr") -> dict:
    if mode not in ("pr", "direct"):
        raise ValueError("mode deve ser 'pr' ou 'direct'")
    cfg = store.cfg
    store.sync(force=True)
    by_id = {m.id: m for m in store.inbox_memories()}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise KeyError(f"ids não encontrados na inbox: {', '.join(missing)}")
    if not ids:
        return {"status": "nada a promover"}

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"promote/{stamp}"
    tmp = Path(tempfile.mkdtemp(prefix="teammem-promote-"))
    wt = tmp / "wt"
    try:
        git("worktree", "add", "-b", branch, str(wt), f"origin/{cfg.main_branch}",
            cwd=cfg.main_dir)
        today = dt.date.today().isoformat()
        for i in ids:
            m = parse((cfg.inbox_dir / by_id[i].inbox_path()).read_text(encoding="utf-8"))
            if mode == "pr":
                m.status, m.last_validated = "validated", today
            else:
                m.status = "provisional"
            dest = wt / m.dest_path()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(m.to_markdown(), encoding="utf-8")
            git("add", m.dest_path(), cwd=wt)
        title = f"memória: promove {len(ids)} item(ns) da inbox"
        body = "\n".join(f"- {i}: {by_id[i].title}" for i in ids) + f"\n\n{TRAILER}"
        store._commit(wt, f"{title}\n\n{body}")

        if mode == "direct":
            git("push", "origin", f"HEAD:{cfg.main_branch}", cwd=wt)
            result = {"status": "promovidas na main", "ids": ids}
        else:
            git("push", "-u", "origin", branch, cwd=wt)
            url = _open_pr(wt, branch, cfg.main_branch, title, body)
            result = {
                "status": "PR aberto" if url else "branch publicada (abra o PR manualmente)",
                "branch": branch,
                "pr": url,
                "ids": ids,
            }
    finally:
        git("worktree", "remove", "--force", str(wt), cwd=cfg.main_dir, check=False)
        if mode == "direct":
            git("branch", "-D", branch, cwd=cfg.main_dir, check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    store.sync(force=True)
    return result


def gc(store: Store) -> dict:
    """Remove da inbox o que já está na main ou expirou (TTL da política)."""
    cfg = store.cfg
    store.sync(force=True)
    ttl = curator.policy_with_defaults(store.policy())["inbox_ttl_days"]
    main_ids = {m.id for m in store.main_memories()}
    removed, expired = [], []
    for m in store.inbox_memories():
        if m.id in main_ids:
            removed.append(m.id)
        elif curator.expired(m, ttl):
            expired.append(m.id)
        else:
            continue
        git("rm", "-q", m.inbox_path(), cwd=cfg.inbox_dir)
    if removed or expired:
        store._commit(cfg.inbox_dir, f"inbox: limpa {len(removed)} promovidas, {len(expired)} expiradas")
        try:
            git("push", "origin", cfg.inbox_branch, cwd=cfg.inbox_dir)
        except GitError as e:
            return {"promovidas_removidas": removed, "expiradas": expired, "erro_push": str(e)}
    return {"promovidas_removidas": removed, "expiradas": expired}


def auto(store: Store) -> dict:
    """Modo particular (CI): auto -> direto na main; humano -> PR; bloqueado -> relatório."""
    verdicts = pending(store)
    auto_ids = [v.memory.id for v in verdicts if v.tier == "auto"]
    human_ids = [v.memory.id for v in verdicts if v.tier == "humano"]
    out: dict = {"bloqueadas": [v.to_dict() for v in verdicts if v.tier == "bloqueado"]}
    if auto_ids:
        out["auto"] = promote(store, auto_ids, mode="direct")
    if human_ids:
        out["humano"] = promote(store, human_ids, mode="pr")
    out["gc"] = gc(store)
    return out
