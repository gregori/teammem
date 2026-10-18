"""Formato das memórias: markdown com frontmatter YAML (ver docs/SPEC.md)."""

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
STATUS = ("provisional", "validated")

_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


class SchemaError(ValueError):
    pass


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "memoria"


def today() -> str:
    return dt.date.today().isoformat()


@dataclass
class Memory:
    id: str
    title: str
    type: str
    scope: str
    body: str
    project: str | None = None
    author: str | None = None
    source: str | None = None
    confidence: str = "medium"
    status: str = "provisional"
    pinned: bool = False
    tags: list[str] = field(default_factory=list)
    created: str = field(default_factory=today)
    last_validated: str | None = None
    review_by: str | None = None
    supersedes: list[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION
    # metadados de leitura (não serializados)
    path: str | None = None
    origin: str = "main"  # "main" (acervo) ou "inbox" (proposta pendente)

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
            raise SchemaError(f"status inválido: {self.status!r}")
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
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "scope": self.scope,
        }
        if self.project:
            fm["project"] = self.project
        fm.update(
            {
                "author": self.author,
                "source": self.source,
                "confidence": self.confidence,
                "status": self.status,
                "pinned": self.pinned,
                "tags": list(self.tags),
                "created": self.created,
                "last_validated": self.last_validated,
                "review_by": self.review_by,
                "supersedes": list(self.supersedes),
                "schema_version": self.schema_version,
            }
        )
        return {k: v for k, v in fm.items() if v not in (None, [])}

    def to_markdown(self) -> str:
        fm = yaml.safe_dump(self.frontmatter(), sort_keys=False, allow_unicode=True).strip()
        return f"---\n{fm}\n---\n\n{self.body.strip()}\n"

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "scope": self.scope,
            "project": self.project,
            "status": "pendente" if self.origin == "inbox" else self.status,
            "pinned": self.pinned,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.frontmatter()
        d["body"] = self.body
        d["path"] = self.path
        d["origin"] = self.origin
        if self.origin == "inbox":
            d["aviso"] = "Proposta pendente de revisão: trate como pista, não como verdade."
        elif self.status == "provisional":
            d["aviso"] = "Memória não revisada por humano: trate como pista, não como verdade."
        return d


def parse(text: str, path: str | None = None, origin: str = "main") -> Memory:
    m = _FM.match(text)
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

    mem = Memory(
        id=s("id") or (Path(path).stem if path else ""),
        title=s("title") or "",
        type=s("type") or "",
        scope=s("scope") or "",
        body=m.group(2).strip(),
        project=s("project"),
        author=s("author"),
        source=s("source"),
        confidence=s("confidence") or "medium",
        status=s("status") or "provisional",
        pinned=bool(fm.get("pinned", False)),
        tags=[str(t) for t in fm.get("tags") or []],
        created=s("created") or today(),
        last_validated=s("last_validated"),
        review_by=s("review_by"),
        supersedes=[str(t) for t in fm.get("supersedes") or []],
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
        project=project,
        author=author,
        source=source,
        confidence=confidence,
        status="provisional",
        pinned=pinned,
        tags=list(tags or []),
        created=created,
        review_by=(dt.date.today() + dt.timedelta(days=review_days)).isoformat(),
    )
    mem.validate()
    return mem
