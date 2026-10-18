"""Curadoria determinística: classifica propostas em auto | humano | bloqueado.

A política vem do `.teammem.yaml` na main do acervo; os padrões abaixo valem
quando o arquivo não existe. O agente (no harness) pode refinar a curadoria
conversando com o revisor; este módulo garante o piso mínimo e reproduzível.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from . import safety
from .schema import Memory

DEFAULT_POLICY = {
    "auto_scopes": ["project"],
    "auto_types": ["gotcha", "pattern", "anti-pattern"],
    "duplicate_threshold": 0.6,
    "inbox_ttl_days": 90,
    "pinned_max": 15,
}

_STOP = set(
    "a o os as um uma de da do das dos e em no na nos nas para por com sem que se "
    "the a an of to in on for with and or is are be not use usar".split()
)


def policy_with_defaults(p: dict | None) -> dict:
    return {**DEFAULT_POLICY, **(p or {})}


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ú0-9_]{3,}", text.lower()) if w not in _STOP}


def similarity(a: Memory, b: Memory) -> float:
    ta, tb = tokens(a.title + " " + a.body), tokens(b.title + " " + b.body)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class Verdict:
    memory: Memory
    tier: str  # "auto" | "humano" | "bloqueado"
    reasons: list[str] = field(default_factory=list)
    similar: list[tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.memory.id,
            "title": self.memory.title,
            "type": self.memory.type,
            "scope": self.memory.scope,
            "project": self.memory.project,
            "author": self.memory.author,
            "created": self.memory.created,
            "nivel": self.tier,
            "motivos": self.reasons,
            "similares": [{"id": i, "similaridade": round(s, 2)} for i, s in self.similar],
        }


def classify(mem: Memory, existing: list[Memory], policy: dict | None = None) -> Verdict:
    pol = policy_with_defaults(policy)
    reasons: list[str] = []

    scan = safety.scan(f"{mem.title}\n{mem.body}")
    if scan.blocked:
        return Verdict(mem, "bloqueado", scan.blocked)
    reasons += scan.review

    similar = sorted(
        ((o.id, s) for o in existing if o.id != mem.id and (s := similarity(mem, o)) >= 0.3),
        key=lambda x: -x[1],
    )[:3]
    if similar and similar[0][1] >= pol["duplicate_threshold"]:
        reasons.append(f"possível duplicata/conflito com {similar[0][0]}")

    if mem.scope not in pol["auto_scopes"]:
        reasons.append(f"escopo {mem.scope} exige revisão humana")
    if mem.type not in pol["auto_types"]:
        reasons.append(f"tipo {mem.type} exige revisão humana")
    if mem.pinned:
        reasons.append("pinned exige revisão humana")
    if mem.supersedes:
        reasons.append("substitui memória existente")

    return Verdict(mem, "humano" if reasons else "auto", reasons, similar)


def expired(mem: Memory, ttl_days: int, today: dt.date | None = None) -> bool:
    today = today or dt.date.today()
    try:
        created = dt.date.fromisoformat(mem.created)
    except ValueError:
        return False
    return (today - created).days > ttl_days


def stale(mem: Memory, today: dt.date | None = None) -> bool:
    today = today or dt.date.today()
    if not mem.review_by:
        return False
    try:
        return dt.date.fromisoformat(mem.review_by) < today
    except ValueError:
        return False
