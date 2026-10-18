import json
import subprocess

import pytest

from teammem import cli, install
from teammem.install import UserPaths

KW = dict(repo="git@x:t/m.git", name="m", source="teammem==0.1.0", server="teammem-m")


def test_install_project_all_harnesses(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".vscode").mkdir()
    (proj / ".vscode" / "mcp.json").write_text('{"servers": {"outro": {"command": "x"}}}')
    res = install.install(list(install.HARNESSES), project_dir=proj, home=tmp_path / "home",
                          **KW)
    assert all(r["status"] == "atualizado" for r in res), res
    vs = json.loads((proj / ".vscode" / "mcp.json").read_text())
    assert "outro" in vs["servers"] and vs["servers"]["teammem-m"]["type"] == "stdio"
    oc = json.loads((proj / "opencode.json").read_text())
    assert oc["mcp"]["teammem-m"]["command"][0] == "uvx"
    assert oc["mcp"]["teammem-m"]["environment"]["TEAMMEM_REPO"] == "git@x:t/m.git"
    toml = (tmp_path / "home" / ".codex" / "config.toml").read_text()
    assert "[mcp_servers.teammem-m]" in toml and 'TEAMMEM_REPO = "git@x:t/m.git"' in toml
    res2 = install.install(list(install.HARNESSES), project_dir=proj, home=tmp_path / "home",
                           **KW)
    assert all(r["status"] == "inalterado" for r in res2)


@pytest.mark.parametrize("system", ["Linux", "Darwin", "Windows"])
def test_install_user_paths(tmp_path, monkeypatch, system):
    home = tmp_path / "home"
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    res = install.install(list(install.HARNESSES), user=True, home=home, system=system,
                          use_claude_cli=False, **KW)
    files = {r["harness"]: r["arquivo"] for r in res}
    assert all(r["status"] == "atualizado" for r in res), res
    assert files["claude"] == str(home / ".claude.json")
    assert files["cursor"] == str(home / ".cursor" / "mcp.json")
    assert files["codex"] == str(home / ".codex" / "config.toml")
    if system == "Linux":
        assert files["copilot"] == str(home / ".config" / "Code" / "User" / "mcp.json")
        assert files["devin"] == str(home / ".config" / "devin" / "mcp_config.json")
        assert files["opencode"] == str(home / ".config" / "opencode" / "opencode.json")
    elif system == "Darwin":
        assert files["copilot"] == str(home / "Library" / "Application Support" / "Code"
                                       / "User" / "mcp.json")
        assert files["devin"] == str(home / ".config" / "devin" / "mcp_config.json")
    else:
        roaming = home / "AppData" / "Roaming"
        assert files["copilot"] == str(roaming / "Code" / "User" / "mcp.json")
        assert files["devin"] == str(roaming / "devin" / "mcp_config.json")


def test_install_does_not_clobber_jsonc(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "mcp.json").write_text("{ // comentário\n}")
    [r] = install.install(["cursor"], project_dir=tmp_path, repo="r", name="m")
    assert r["status"] == "manual" and "mcpServers" in r["trecho"]


def test_skills_user_and_project(tmp_path):
    paths = UserPaths.detect(tmp_path / "home", "Linux")
    written = install.install_skill(list(install.HARNESSES), user=True, paths=paths)
    assert str(tmp_path / "home" / ".claude" / "skills" / "learn" / "SKILL.md") in written
    assert str(tmp_path / "home" / ".agents" / "skills" / "learn" / "SKILL.md") in written
    assert len(written) == 3  # claude, agents, cursor
    proj = install.install_skill(["claude", "devin"], project_dir=tmp_path / "p")
    assert len(proj) == 2


def test_instruction_targets_avoid_duplicates(tmp_path):
    paths = UserPaths.detect(tmp_path, "Linux")
    files, notes = install.instruction_targets(list(install.HARNESSES), paths)
    names = [str(f.relative_to(tmp_path)) for f in files]
    # Devin e OpenCode leem o CLAUDE.md global: não duplicar o bloco
    assert ".claude/CLAUDE.md" in names and ".codex/AGENTS.md" in names
    assert ".config/devin/AGENTS.md" not in names
    assert ".config/opencode/AGENTS.md" not in names
    assert ".copilot/copilot-instructions.md" in names
    assert len(notes) == 3
    # sem Claude, cada um ganha o próprio arquivo
    files, _ = install.instruction_targets(["devin", "opencode"], paths)
    assert {f.name for f in files} == {"AGENTS.md"} and len(files) == 2


def test_claude_import(tmp_path):
    assert install.ensure_claude_import(tmp_path)
    assert not install.ensure_claude_import(tmp_path)


def test_init_new_and_into_existing_clone(tmp_path):
    cli.main(["init", str(tmp_path / "novo"), "--profile", "personal"])
    novo = tmp_path / "novo"
    assert (novo / ".git").exists() and (novo / ".teammem.yaml").exists()
    assert (novo / ".github" / "workflows" / "teammem-curate.yml").exists()
    assert not (novo / ".github" / "CODEOWNERS").exists()

    clone = tmp_path / "clone"
    subprocess.run(["git", "init", "-q", str(clone)], check=True)
    (clone / "README.md").write_text("meu readme\n")
    cli.main(["init", str(clone), "--profile", "work"])
    assert (clone / "README.md").read_text() == "meu readme\n"  # não sobrescreve
    assert (clone / ".github" / "CODEOWNERS").exists()
    assert not (clone / ".github" / "workflows").exists()
    assert "auto_scopes: [project]" in (clone / ".teammem.yaml").read_text()

    other = tmp_path / "outro"
    other.mkdir()
    (other / "x").write_text("x")
    with pytest.raises(SystemExit):
        cli.main(["init", str(other)])
