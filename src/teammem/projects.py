"""Identidade de projeto.

O projeto atual é resolvido nesta ordem:

1. override explícito (`--project` ou `TEAMMEM_PROJECT`);
2. nota de projeto (`projects/<slug>.md` no acervo) cujo `remotes` contém a URL
   normalizada do `origin` do repositório atual;
3. nota de projeto cujo slug ou `aliases` coincide com o nome da pasta git;
4. nome da pasta git (compatível com acervos anteriores às notas).

A identidade é sempre o **slug** (ver `key`). Toda comparação de projeto usa
`key()` dos dois lados, o que elimina a divergência entre o nome usado no
filtro e o nome usado no caminho do arquivo.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .schema import FM_RE, slugify

PROJECTS_DIR = "projects"


def key(project: str | None) -> str | None:
    """Forma canônica de um identificador de projeto."""
    return slugify(project) if project else None


def same(a: str | None, b: str | None) -> bool:
    return bool(a and b) and key(a) == key(b)


_SCP = re.compile(r"^(?:[\w.\-]+@)?([\w.\-]+):(?!/)(.+)$")  # git@host:owner/repo


def normalize_remote(url: str | None) -> str | None:
    """`git@github.com:Org/Repo.git` e `https://user@github.com/org/repo/` viram
    `github.com/org/repo`. Remove credenciais, porta, `.git` e barras finais."""
    if not url:
        return None
    u = url.strip()
    if not u:
        return None
    m = _SCP.match(u)
    if m and "://" not in u:
        host, path = m.group(1), m.group(2)
    else:
        u = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", u, flags=re.I)  # esquema
        if u.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", u):  # caminho local
            host, path = "", u
        else:
            host, _, path = u.partition("/")
            host = host.rsplit("@", 1)[-1].split(":", 1)[0]  # credenciais e porta
    path = re.sub(r"\.git/?$", "", path.replace("\\", "/")).strip("/")
    parts = [p for p in (host, path) if p]
    return "/".join(parts).lower() or None


def _git(args: list[str], cwd: str | Path | None) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd,
                             timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def detect_remote(cwd: str | Path | None = None) -> str | None:
    return normalize_remote(_git(["config", "--get", "remote.origin.url"], cwd))


def detect_folder(cwd: str | Path | None = None) -> str | None:
    top = _git(["rev-parse", "--show-toplevel"], cwd)
    return Path(top).name if top else None


@dataclass
class ProjectNote:
    slug: str
    title: str
    description: str = ""
    remotes: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    path: str | None = None

    def to_markdown(self, body: str = "") -> str:
        fm = {
            "type": "project",
            "title": self.title,
            "description": self.description or f"Projeto {self.title}",
            "remotes": self.remotes,
            "aliases": self.aliases,
        }
        text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
        body = body.strip() or (
            "Nota de identidade do projeto. Liste em `remotes` as URLs normalizadas "
            "(host/dono/repo) dos repositórios que pertencem a ele."
        )
        return f"---\n{text}\n---\n\n{body}\n"


def parse_note(text: str, path: str) -> ProjectNote | None:
    m = FM_RE.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict) or fm.get("type") != "project":
        return None
    slug = key(Path(path).stem) or ""
    return ProjectNote(
        slug=slug,
        title=str(fm.get("title") or slug),
        description=str(fm.get("description") or ""),
        remotes=[r for r in (normalize_remote(str(x)) for x in fm.get("remotes") or []) if r],
        aliases=[key(str(a)) or "" for a in fm.get("aliases") or []],
        path=path,
    )


def load_notes(root: Path) -> list[ProjectNote]:
    base = root / PROJECTS_DIR
    notes = []
    if base.exists():
        for f in sorted(base.glob("*.md")):
            if f.name in ("index.md", "log.md"):
                continue
            try:
                n = parse_note(f.read_text(encoding="utf-8"), f"{PROJECTS_DIR}/{f.name}")
            except UnicodeDecodeError:
                n = None
            if n:
                notes.append(n)
    return notes


@dataclass
class Resolution:
    project: str | None
    how: str  # override | remote | alias | pasta | nenhum
    remote: str | None = None
    folder: str | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return {"projeto": self.project, "como": self.how, "remote": self.remote,
                "pasta": self.folder, "nota": self.note}


def resolve(override: str | None, remote: str | None, folder: str | None,
            notes: list[ProjectNote]) -> Resolution:
    if override:
        return Resolution(key(override), "override", remote, folder)
    if remote:
        for n in notes:
            if remote in n.remotes:
                return Resolution(n.slug, "remote", remote, folder, n.path)
    fk = key(folder)
    if fk:
        for n in notes:
            if fk == n.slug or fk in n.aliases:
                return Resolution(n.slug, "alias", remote, folder, n.path)
        return Resolution(fk, "pasta", remote, folder)
    return Resolution(None, "nenhum", remote, folder)


def suggest_note(res: Resolution) -> ProjectNote | None:
    """Nota sugerida para o repositório atual, quando ainda não há uma."""
    if not res.project or res.how in ("remote", "override"):
        return None
    return ProjectNote(slug=res.project, title=res.folder or res.project,
                       remotes=[res.remote] if res.remote else [])
