import json

from teammem import install


def test_install_all_harnesses(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".vscode").mkdir()
    (proj / ".vscode" / "mcp.json").write_text('{"servers": {"outro": {"command": "x"}}}')
    res = install.install(list(install.HARNESSES), project_dir=proj, repo="git@x:t/m.git",
                          name="m", source="teammem==0.1.0", server="teammem-m",
                          home=tmp_path / "home")
    assert all(r["status"] == "atualizado" for r in res), res
    vs = json.loads((proj / ".vscode" / "mcp.json").read_text())
    assert "outro" in vs["servers"] and vs["servers"]["teammem-m"]["type"] == "stdio"
    oc = json.loads((proj / "opencode.json").read_text())
    assert oc["mcp"]["teammem-m"]["command"][0] == "uvx"
    toml = (tmp_path / "home" / ".codex" / "config.toml").read_text()
    assert "[mcp_servers.teammem-m]" in toml and 'TEAMMEM_REPO = "git@x:t/m.git"' in toml
    # idempotente
    res2 = install.install(list(install.HARNESSES), project_dir=proj, repo="git@x:t/m.git",
                           name="m", source="teammem==0.1.0", server="teammem-m",
                           home=tmp_path / "home")
    assert all(r["status"] == "inalterado" for r in res2)


def test_install_does_not_clobber_jsonc(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "mcp.json").write_text("{ // comentário\n}")
    [r] = install.install(["cursor"], project_dir=tmp_path, repo="r", name="m")
    assert r["status"] == "manual" and "mcpServers" in r["trecho"]


def test_skill_and_claude_import(tmp_path):
    written = install.install_skill(tmp_path, ["claude", "devin"])
    assert len(written) == 2
    assert install.ensure_claude_import(tmp_path)
    assert not install.ensure_claude_import(tmp_path)
