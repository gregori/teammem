"""Configuração: flags da CLI > variáveis de ambiente > padrões.

Nenhuma URL fica fixa no código: o repositório de memórias, o índice de pacotes
e o marketplace vêm sempre de configuração (requisito do ambiente corporativo).
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


def _git_config(key: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "config", "--get", key], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _repo_name(repo: str) -> str:
    name = re.split(r"[/:]", repo.rstrip("/"))[-1]
    return re.sub(r"\.git$", "", name) or "memory"


def detect_project(cwd: str | os.PathLike | None = None) -> str | None:
    """Nome do projeto atual = nome da pasta raiz do git em cwd."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=cwd or os.getcwd(),
            timeout=5,
        )
        top = out.stdout.strip()
        return Path(top).name if top else None
    except (OSError, subprocess.TimeoutExpired):
        return None


@dataclass
class Config:
    repo: str
    name: str
    home: Path
    author: str | None
    project: str | None
    main_branch: str = "main"
    inbox_branch: str = "inbox"
    sync_seconds: int = 600

    @property
    def base(self) -> Path:
        return self.home / self.name

    @property
    def main_dir(self) -> Path:
        return self.base / "main"

    @property
    def inbox_dir(self) -> Path:
        return self.base / "inbox"

    @property
    def index_path(self) -> Path:
        return self.base / "index.sqlite"


def load(
    repo: str | None = None,
    name: str | None = None,
    home: str | None = None,
    author: str | None = None,
    project: str | None = None,
) -> Config:
    repo = repo or os.environ.get("TEAMMEM_REPO")
    if not repo:
        raise SystemExit(
            "Repositório de memórias não configurado: use --repo ou TEAMMEM_REPO "
            "(URL git ou caminho local)."
        )
    return Config(
        repo=repo,
        name=name or os.environ.get("TEAMMEM_NAME") or _repo_name(repo),
        home=Path(home or os.environ.get("TEAMMEM_HOME") or Path.home() / ".teammem").expanduser(),
        author=author or os.environ.get("TEAMMEM_AUTHOR") or _git_config("user.name"),
        project=project or os.environ.get("TEAMMEM_PROJECT") or detect_project(),
        main_branch=os.environ.get("TEAMMEM_MAIN_BRANCH", "main"),
        inbox_branch=os.environ.get("TEAMMEM_INBOX_BRANCH", "inbox"),
        sync_seconds=int(os.environ.get("TEAMMEM_SYNC_SECONDS", "600")),
    )
