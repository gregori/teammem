import subprocess
from pathlib import Path

import pytest

from teammem.config import Config
from teammem.service import Service


def sh(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """Repositório 'remoto' bare com um acervo inicial na main."""
    bare = tmp_path / "remote.git"
    sh("git", "init", "-q", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    sh("git", "clone", "-q", str(bare), str(seed))
    (seed / ".teammem.yaml").write_text(
        "auto_scopes: [project, global]\nauto_types: [gotcha, pattern, anti-pattern]\n"
    )
    (seed / "team").mkdir()
    (seed / "team" / "2026-01-01-ana-migrations.md").write_text(
        "---\nid: 2026-01-01-ana-migrations\ntitle: Nunca rode migrations em homologação\n"
        "type: convention\nscope: team\nauthor: ana\nstatus: validated\npinned: true\n"
        "created: '2026-01-01'\n---\n\nUse o Postgres do docker compose; o .env padrão aponta "
        "para homologação compartilhada.\n"
    )
    sh("git", "add", "-A", cwd=seed)
    sh("git", "-c", "user.name=seed", "-c", "user.email=s@x", "commit", "-qm", "seed", cwd=seed)
    sh("git", "push", "-q", "origin", "main", cwd=seed)
    return bare


def make_cfg(tmp_path: Path, remote: Path, user: str, project: str = "api") -> Config:
    return Config(
        repo=str(remote),
        name="acervo",
        home=tmp_path / f"home-{user}",
        author=user,
        project=project,
        sync_seconds=0,
    )


@pytest.fixture
def alice(tmp_path, remote, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "a@x")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "a@x")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "x")
    return Service(make_cfg(tmp_path, remote, "alice"))


@pytest.fixture
def bob(tmp_path, remote, monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "b@x")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "b@x")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "x")
    return Service(make_cfg(tmp_path, remote, "bob"))
