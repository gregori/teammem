"""Checagens de segurança aplicadas no `propose` e de novo na curadoria.

- Segredos: bloqueiam a proposta.
- Instruções dirigidas ao agente (prompt injection): bloqueiam.
- Comandos de shell e URLs: não bloqueiam, mas forçam revisão humana.

Memórias são lidas por agentes de todo o time; um texto malicioso aqui vira
vetor de ataque para todos. Por isso o MCP também entrega memórias como dados,
nunca como instruções.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "gitlab_token": re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "openai_like_key": re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    "credential_assignment": re.compile(
        r"(?i)\b(password|passwd|senha|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[^\s'\"<>]{8,}"
    ),
}

INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.I)
    for p in (
        r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
        r"ignore (as |todas as )?instru[cç][oõ]es (anteriores|acima)",
        r"disregard (the )?(system|previous) (prompt|instructions)",
        r"\bsystem prompt\b",
        r"you are now\b",
        r"voc[eê] agora [eé]\b",
        r"do not (tell|inform) the user",
        r"n[aã]o (conte|informe|avise) (ao|o) usu[aá]rio",
        r"<\s*/?\s*(system|assistant)\s*>",
    )
]

REVIEW_PATTERNS: dict[str, re.Pattern[str]] = {
    "url": re.compile(r"https?://\S+"),
    "pipe_to_shell": re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b"),
    "destructive_command": re.compile(
        r"\b(rm\s+-rf|git\s+push\s+--force|drop\s+table|truncate\s+table|chmod\s+777)\b", re.I
    ),
}


@dataclass
class ScanResult:
    blocked: list[str] = field(default_factory=list)
    review: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocked


def scan(text: str) -> ScanResult:
    r = ScanResult()
    for name, pat in SECRET_PATTERNS.items():
        if pat.search(text):
            r.blocked.append(f"possível segredo ({name})")
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            r.blocked.append("texto com cara de instrução para o agente (prompt injection)")
            break
    for name, pat in REVIEW_PATTERNS.items():
        if pat.search(text):
            r.review.append(f"contém {name.replace('_', ' ')}")
    return r
