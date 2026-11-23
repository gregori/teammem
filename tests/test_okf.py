import subprocess
from pathlib import Path

import pytest

from teammem import agentsmd, cli, config, okf, projects, review
from teammem.projects import ProjectNote, normalize_remote, resolve
from teammem.schema import parse
from teammem.store import git, load_memories

V1 = (
    "---\nid: 2026-01-02-ana-retry\ntitle: Cliente HTTP já faz retry\ntype: gotcha\n"
    "scope: project\nproject: API Pedidos\nauthor: ana\nsource: https://git/x/pull/1\n"
    "status: validated\nlast_validated: '2026-02-01'\nreview_by: '2026-08-01'\n"
    "created: '2026-01-02'\nschema_version: 1\n---\n\nNão use tenacity. Configure no cliente.\n"
)


@pytest.mark.parametrize("url,expected", [
    ("git@github.com:Gregori/TeamMem.git", "github.com/gregori/teammem"),
    ("https://github.com/gregori/teammem", "github.com/gregori/teammem"),
    ("https://user:tok@github.com/gregori/teammem.git/", "github.com/gregori/teammem"),
    ("ssh://git@git.empresa:2222/grupo/sub/api.git", "git.empresa/grupo/sub/api"),
    ("/srv/git/acervo.git", "srv/git/acervo"),
    ("", None),
])
def test_normalize_remote(url, expected):
    assert normalize_remote(url) == expected


def test_resolve_order():
    notes = [ProjectNote(slug="api-pedidos", title="API de pedidos",
                         remotes=["github.com/zup/api-pedidos"], aliases=["pedidos"])]
    assert resolve("Outro Nome", "github.com/zup/api-pedidos", "x", notes).how == "override"
    r = resolve(None, "github.com/zup/api-pedidos", "clone-qualquer", notes)
    assert (r.project, r.how) == ("api-pedidos", "remote")
    r = resolve(None, "github.com/fork/api", "pedidos", notes)
    assert (r.project, r.how) == ("api-pedidos", "alias")
    r = resolve(None, None, "Minha Pasta", notes)
    assert (r.project, r.how) == ("minha-pasta", "pasta")
    assert resolve(None, None, None, notes).project is None


def test_parse_v1_converts_to_okf():
    m = parse(V1, path="project/api-pedidos/2026-01-02-ana-retry.md")
    assert m.status == "stable" and m.validated and m.curation == "validated"
    assert m.verified == [{"by": "human:ana", "at": "2026-02-01T00:00:00+00:00"}]
    assert m.sources == ["https://git/x/pull/1"]
    assert m.stale_after == "2026-08-01T00:00:00+00:00"
    fm = parse(m.to_markdown()).frontmatter()
    assert list(fm)[:3] == ["type", "title", "description"]
    assert fm["description"] == "Não use tenacity."
    assert "review_by" not in fm and "source" not in fm


def test_project_key_mismatch_is_fixed(alice):
    """Memória gravada com o nome cru ('API Pedidos') aparece para o slug."""
    alice.refresh(force=True)
    mem = parse(V1)
    path = alice.cfg.main_dir / mem.dest_path()
    path.parent.mkdir(parents=True)
    path.write_text(V1)
    alice.cfg.project = "api-pedidos"
    alice._index = None
    assert any(i["id"] == mem.id for i in alice.list_index())
    assert alice.search("tenacity")[0]["id"] == mem.id


def test_identity_by_remote_note(alice, remote, tmp_path):
    seed = tmp_path / "seed"
    (seed / "projects").mkdir()
    (seed / "projects" / "pedidos.md").write_text(ProjectNote(
        slug="pedidos", title="Pedidos", remotes=["github.com/zup/api-pedidos"]).to_markdown())
    subprocess.run(["git", "add", "-A"], cwd=seed, check=True)
    subprocess.run(["git", "-c", "user.name=s", "-c", "user.email=s@x", "commit", "-qm", "nota"],
                   cwd=seed, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=seed, check=True)
    alice.cfg.project, alice.cfg.remote, alice.cfg.folder = None, "github.com/zup/api-pedidos", "x"
    alice.refresh(force=True)
    assert alice.resolve_project().to_dict()["como"] == "remote"
    r = alice.propose(title="Paginação por cursor", body="Offset estoura.", type="pattern")
    assert r["status"] == "publicada"
    assert alice.store.inbox_memories()[0].project == "pedidos"


def test_promotion_writes_okf_files(alice):
    alice.propose(title="Lib X quebra com fontes CID", body="Use a lib Y para PDF.",
                  type="gotcha")
    alice.propose(title="Escolhemos Postgres", body="Transações entre agregados.",
                  type="decision", scope="team")
    by_title = {m.title: m.id for m in alice.store.inbox_memories()}
    review.promote(alice.store, [by_title["Lib X quebra com fontes CID"]], mode="direct")
    main = alice.cfg.main_dir
    root_index = (main / "index.md").read_text()
    assert root_index.startswith('---\nokf_version: "0.2"\n---')
    proj_index = (main / "project" / "api" / "index.md").read_text()
    assert "[Lib X quebra com fontes CID](/project/api/" in proj_index
    assert "não revisada" in proj_index
    log = (main / "log.md").read_text()
    assert "**Promoção**: [Lib X quebra com fontes CID]" in log
    # o seed do conftest tem uma memória v1: o bundle continua conforme
    assert okf.validate_bundle(main) == []

    res = review.promote(alice.store, [by_title["Escolhemos Postgres"]], mode="pr")
    changed = git("diff", "--name-only", f"origin/main...origin/{res['branch']}",
                  cwd=main).split()
    assert {"team/index.md", "log.md", "index.md"} <= set(changed)
    body = git("show", f"origin/{res['branch']}:team/{by_title['Escolhemos Postgres']}.md",
               cwd=main)
    assert "by: human:alice" in body
    assert by_title["Escolhemos Postgres"] in review.in_flight(alice.store)
    assert "index" not in review.in_flight(alice.store)


def test_log_groups_by_date(tmp_path):
    import datetime as dt

    okf.prepend_log(tmp_path, ["* a"], dt.date(2026, 1, 1))
    okf.prepend_log(tmp_path, ["* b"], dt.date(2026, 1, 2))
    okf.prepend_log(tmp_path, ["* c"], dt.date(2026, 1, 2))
    text = (tmp_path / "log.md").read_text()
    assert text.index("## 2026-01-02") < text.index("## 2026-01-01")
    assert text.index("* c") < text.index("* b") < text.index("* a")
    assert okf.validate_bundle(tmp_path) == []


def test_migrate_v1_bundle(tmp_path, capsys):
    root = tmp_path / "acervo"
    (root / "project" / "API Pedidos").mkdir(parents=True)
    (root / "project" / "API Pedidos" / "2026-01-02-ana-retry.md").write_text(V1)
    (root / "README.md").write_text("# acervo\n")
    cli.main(["migrate", str(root)])
    assert okf.validate_bundle(root) == []
    note = projects.load_notes(root)
    assert [n.slug for n in note] == ["api-pedidos"]
    m = load_memories(root)[0]
    assert m.project == "api-pedidos" and m.validated
    assert (root / "index.md").exists() and "Migração" in (root / "log.md").read_text()
    log_before = (root / "log.md").read_text()
    cli.main(["migrate", str(root)])  # idempotente
    assert (root / "log.md").read_text() == log_before


def test_init_is_conformant(tmp_path):
    cli.main(["init", str(tmp_path / "novo")])
    root = tmp_path / "novo"
    assert okf.validate_bundle(root) == []
    assert (root / "projects" / "index.md").exists()


def test_validate_reports_problems(tmp_path):
    (tmp_path / "global").mkdir()
    (tmp_path / "global" / "x.md").write_text("---\ntitle: sem tipo\n---\n\ncorpo\n")
    (tmp_path / "global" / "index.md").write_text("---\nokf_version: '0.2'\n---\n# x\n")
    (tmp_path / "log.md").write_text("# log\n## ontem\n")
    found = {p.path for p in okf.validate_bundle(tmp_path)}
    assert found == {"global/x.md", "global/index.md", "log.md"}


def test_indexes_drop_empty_project(tmp_path):
    (tmp_path / "project" / "velho").mkdir(parents=True)
    (tmp_path / "project" / "velho" / "index.md").write_text("# velho\n")
    changed = okf.write_indexes(tmp_path, [], [])
    assert "project/velho/index.md" in changed
    assert not (tmp_path / "project" / "velho" / "index.md").exists()
    assert okf.write_indexes(tmp_path, [], []) == []  # determinístico


def test_config_discovers_single_acervo(tmp_path, monkeypatch, alice):
    alice.refresh(force=True)
    monkeypatch.delenv("TEAMMEM_REPO", raising=False)
    monkeypatch.delenv("TEAMMEM_NAME", raising=False)
    cfg = config.load(home=str(alice.cfg.home))
    assert cfg.name == "acervo" and cfg.repo == alice.cfg.repo
    with pytest.raises(SystemExit):
        config.load(home=str(tmp_path / "vazio"))


def test_agents_md_cli_mode():
    block = agentsmd.render([], "pessoal", "teammem-pessoal", mode="cli",
                            cli="teammem", main_dir="/h/.teammem/pessoal/main")
    assert "`/h/.teammem/pessoal/main`" in block
    assert "teammem search --name pessoal" in block and "MCP" not in block
    assert "Nunca crie nem" in block
