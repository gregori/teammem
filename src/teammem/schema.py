"""Formato das memórias: conceitos OKF v0.2 (markdown com frontmatter YAML).

Ver docs/SPEC.md. Campos do OKF (`type`, `title`, `description`, `tags`,
`status`, `sources`, `verified`, `stale_after`) seguem a spec; os demais
(`id`, `scope`, `project`, `author`, `confidence`, `pinned`, `created`,
`supersedes`, `schema_version`) são extensões do teammem, permitidas pelo OKF.

A leitura aceita também o formato v1 (`status: provisional|validated`,
`source`, `review_by`, `last_validated`) e o converte em memória.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import SCHEMA_VERSION

TYPES = ("decision", "gotcha", "convention", "pattern", "anti-pattern")
SCOPES = ("global", "team", "org", "project")
CONFIDENCE = ("low", "medium", "high")
STATUS = ("draft", "stable", "deprecated")  # valores do OKF
RESERVED = ("index.md", "log.md")  # nomes reservados pelo OKF

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


class SchemaError(ValueError):
    pass


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "memoria"


def today() -> str:
    return dt.date.today().isoformat()


def iso_datetime(date: str | dt.date | None = None) -> str:
    """Data ISO -> datetime ISO 8601 com offset UTC explícito (exigência do OKF)."""
    if date is None:
        return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    d = date if isinstance(date, dt.date) else dt.date.fromisoformat(str(date)[:10])
    return f"{d.isoformat()}T00:00:00+00:00"


def human(name: str | None) -> str:
    return f"human:{slugify(name or 'desconhecido', 32)}"


def derive_description(body: str, max_len: int = 160) -> str:
    """Primeira frase do corpo, em uma linha (o OKF usa `description` nos índices)."""
    text = " ".join(body.split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    first = m.group(1) if m else text
    if len(first) > max_len:
        first = first[: max_len - 1].rstrip() + "…"
    return first


def _str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [str(v)]


@dataclass
class Memory:
    id: str
    title: str
    type: str
    scope: str
    body: str
    description: str = ""
    project: str | None = None
    author: str | None = None
    sources: list[str] = field(default_factory=list)
    confidence: str = "medium"
    status: str = "draft"
    verified: list[dict] = field(default_factory=list)
    pinned: bool = False
    tags: list[str] = field(default_factory=list)
    created: str = field(default_factory=today)
    stale_after: str | None = None
    supersedes: list[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION
    # metadados de leitura (não serializados)
    path: str | None = None
    origin: str = "main"  # "main" (acervo) ou "inbox" (proposta pendente)

    # ---------- estado de curadoria (derivado) ----------
    @property
    def validated(self) -> bool:
        """Revisada por humano: há um `verified` com ator `human:` (OKF §5.3)."""
        return any(str(v.get("by", "")).startswith("human:") for v in self.verified)

    @property
    def curation(self) -> str:
        if self.origin == "inbox":
            return "pendente"
        return "validated" if self.validated else "provisional"

    @property
    def source(self) -> str | None:
        return self.sources[0] if self.sources else None

    def verify(self, by: str, at: str | None = None) -> None:
        self.verified.append({"by": by, "at": at or iso_datetime()})

    # ---------- validação ----------
    def validate(self) -> None:
        if not self.title.strip():
            raise SchemaError("title vazio")
        if self.type not in TYPES:
            raise SchemaError(f"type inválido: {self.type!r} (use {', '.join(TYPES)})")
        if self.scope not in SCOPES:
            raise SchemaError(f"scope inválido: {self.scope!r} (use {', '.join(SCOPES)})")
        if self.scope == "project" and not self.project:
            raise SchemaError("scope=project exige o campo project")
        if self.confidence not in CONFIDENCE:
            raise SchemaError(f"confidence inválido: {self.confidence!r}")
        if self.status not in STATUS:
            raise SchemaError(f"status inválido: {self.status!r} (use {', '.join(STATUS)})")
        if not self.body.strip():
            raise SchemaError("corpo vazio")

    # ---------- caminhos ----------
    def dest_path(self) -> str:
        """Caminho da memória no acervo (branch main)."""
        if self.scope == "project":
            return f"project/{slugify(self.project or '')}/{self.id}.md"
        return f"{self.scope}/{self.id}.md"

    def inbox_path(self) -> str:
        return f"inbox/{self.id}.md"

    # ---------- serialização ----------
    def frontmatter(self) -> dict[str, Any]:
        fm: dict[str, Any] = {
            # OKF
            "type": self.type,
            "title": self.title,
            "description": self.description or derive_description(self.body),
            "tags": list(self.tags),
            "status": self.status,
            "sources": [{"resource": s} for s in self.sources],
            "verified": [dict(v) for v in self.verified],
            "stale_after": self.stale_after,
            # extensões teammem
            "id": self.id,
            "scope": self.scope,
            "project": self.project,
            "author": self.author,
            "confidence": self.confidence,
            "pinned": self.pinned,
            "created": self.created,
            "supersedes": list(self.supersedes),
            "schema_version": self.schema_version,
        }
        return {k: v for k, v in fm.items() if v not in (None, [])}

    def to_markdown(self) -> str:
        fm = yaml.safe_dump(self.frontmatter(), sort_keys=False, allow_unicode=True).strip()
        return f"---\n{fm}\n---\n\n{self.body.strip()}\n"

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description or derive_description(self.body),
            "type": self.type,
            "scope": self.scope,
            "project": self.project,
            "status": self.curation,
            "pinned": self.pinned,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.frontmatter()
        d["body"] = self.body
        d["path"] = self.path
        d["origin"] = self.origin
        d["curadoria"] = self.curation
        if self.origin == "inbox":
            d["aviso"] = "Proposta pendente de revisão: trate como pista, não como verdade."
        elif not self.validated:
            d["aviso"] = "Memória não revisada por humano: trate como pista, não como verdade."
        return d


def _sources(fm: dict) -> list[str]:
    out = []
    for s in fm.get("sources") or []:
        if isinstance(s, dict) and s.get("resource"):
            out.append(str(s["resource"]))
        elif isinstance(s, str):
            out.append(s)
    if fm.get("source"):  # v1
        out.append(str(fm["source"]))
    return list(dict.fromkeys(out))


def _verified(fm: dict) -> list[dict]:
    v = fm.get("verified")
    if isinstance(v, dict):  # OKF: mapa único = lista de um elemento
        v = [v]
    out = [{"by": str(x.get("by")), "at": str(x.get("at"))}
           for x in v or [] if isinstance(x, dict) and x.get("by")]
    if fm.get("status") == "validated" and not out:  # v1
        out.append({"by": human(fm.get("author")),
                    "at": iso_datetime(fm.get("last_validated") or fm.get("created") or today())})
    return out


def parse(text: str, path: str | None = None, origin: str = "main") -> Memory:
    m = FM_RE.match(text)
    if not m:
        raise SchemaError(f"{path or 'memória'}: frontmatter ausente")
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:  # pragma: no cover - mensagem do yaml
        raise SchemaError(f"{path}: YAML inválido: {e}") from e
    if not isinstance(fm, dict):
        raise SchemaError(f"{path}: frontmatter não é um mapa")

    def s(key: str) -> str | None:
        v = fm.get(key)
        return None if v is None else str(v)

    status = s("status") or "stable"  # OKF: ausente = stable
    if status in ("provisional", "validated"):  # v1
        status = "draft" if origin == "inbox" else "stable"
    stale = s("stale_after") or (iso_datetime(s("review_by")) if s("review_by") else None)
    body = m.group(2).strip()

    mem = Memory(
        id=s("id") or (Path(path).stem if path else ""),
        title=s("title") or "",
        type=s("type") or "",
        scope=s("scope") or "",
        body=body,
        description=s("description") or "",
        project=s("project"),
        author=s("author"),
        sources=_sources(fm),
        confidence=s("confidence") or "medium",
        status=status,
        verified=_verified(fm),
        pinned=bool(fm.get("pinned", False)),
        tags=_str_list(fm.get("tags")),
        created=s("created") or today(),
        stale_after=stale,
        supersedes=_str_list(fm.get("supersedes")),
        schema_version=int(fm.get("schema_version", SCHEMA_VERSION)),
        path=path,
        origin=origin,
    )
    mem.validate()
    return mem


def new_memory(
    *,
    title: str,
    body: str,
    type: str,
    scope: str,
    project: str | None = None,
    author: str | None = None,
    source: str | None = None,
    confidence: str = "medium",
    tags: list[str] | None = None,
    pinned: bool = False,
    description: str | None = None,
    review_days: int = 180,
) -> Memory:
    created = today()
    author_slug = slugify(author or "anon", 16)
    mem = Memory(
        id=f"{created}-{author_slug}-{slugify(title, 40)}",
        title=title.strip(),
        type=type,
        scope=scope,
        body=body.strip(),
        description=(description or "").strip() or derive_description(body),
        project=project,
        author=author,
        sources=[source] if source else [],
        confidence=confidence,
        status="draft",
        pinned=pinned,
        tags=list(tags or []),
        created=created,
        stale_after=iso_datetime(dt.date.today() + dt.timedelta(days=review_days)),
    )
    mem.validate()
    return mem
