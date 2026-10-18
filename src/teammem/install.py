"""Instalador multi-harness: escreve/mescla a config de MCP de cada ferramenta.

Idempotente. Nunca sobrescreve um arquivo que não consegue interpretar (ex.:
JSON com comentários): nesse caso devolve o trecho para colar manualmente.

Formatos (verifique em cada atualização das ferramentas):
- Claude Code  .mcp.json                {"mcpServers": {...}}
- Cursor       .cursor/mcp.json         {"mcpServers": {...}}
- Copilot      .vscode/mcp.json         {"servers": {..., "type": "stdio"}}
- Devin CLI    .devin/mcp_config.json   {"mcpServers": {...}}
- OpenCode     opencode.json            {"mcp": {..., "type": "local", "command": [...]}}
- Codex        ~/.codex/config.toml     [mcp_servers.<nome>]
"""

from __future__ import annotations

import json
import re
import shutil
from importlib import resources
from pathlib import Path

HARNESSES = ("claude", "cursor", "copilot", "devin", "opencode", "codex")


def server_cmd(source: str, repo: str, name: str) -> tuple[str, list[str], dict[str, str]]:
    """Comando que cada harness executa. `source` permite registry interno,
    git interno ou wheel local: ex. 'teammem==0.1.0', 'git+https://…', './dist/x.whl'."""
    args = ["--from", source, "teammem", "serve"]
    return "uvx", args, {"TEAMMEM_REPO": repo, "TEAMMEM_NAME": name}


def _merge_json(path: Path, key: str, server: str, entry: dict) -> dict:
    data: dict = {}
    if path.exists() and path.read_text(encoding="utf-8").strip():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            snippet = json.dumps({key: {server: entry}}, indent=2, ensure_ascii=False)
            return {"arquivo": str(path), "status": "manual", "trecho": snippet}
    before = json.dumps(data, sort_keys=True)
    data.setdefault(key, {})[server] = entry
    if json.dumps(data, sort_keys=True) == before:
        return {"arquivo": str(path), "status": "inalterado"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"arquivo": str(path), "status": "atualizado"}


def _codex_toml(path: Path, server: str, cmd: str, args: list[str], env: dict) -> dict:
    def q(s: str) -> str:
        return json.dumps(s, ensure_ascii=False)

    block = (
        f"# teammem:{server}:start\n"
        f"[mcp_servers.{server}]\n"
        f"command = {q(cmd)}\n"
        f"args = [{', '.join(q(a) for a in args)}]\n\n"
        f"[mcp_servers.{server}.env]\n"
        + "".join(f"{k} = {q(v)}\n" for k, v in env.items())
        + f"# teammem:{server}:end\n"
    )
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    pat = re.compile(rf"# teammem:{re.escape(server)}:start\n.*?# teammem:{re.escape(server)}:end\n",
                     re.S)
    if pat.search(old):
        new = pat.sub(lambda _: block, old)
    elif f"[mcp_servers.{server}]" in old:
        return {"arquivo": str(path), "status": "manual", "trecho": block}
    else:
        new = (old.rstrip() + "\n\n" if old.strip() else "") + block
    if new == old:
        return {"arquivo": str(path), "status": "inalterado"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8")
    return {"arquivo": str(path), "status": "atualizado"}


def install(
    harnesses: list[str],
    *,
    project_dir: Path,
    repo: str,
    name: str,
    source: str = "teammem",
    server: str | None = None,
    home: Path | None = None,
) -> list[dict]:
    home = home or Path.home()
    server = server or ("teammem" if name in ("memory", "teammem") else f"teammem-{name}")
    cmd, args, env = server_cmd(source, repo, name)
    std = {"command": cmd, "args": args, "env": env}
    out = []
    for h in harnesses:
        if h == "claude":
            r = _merge_json(project_dir / ".mcp.json", "mcpServers", server, std)
        elif h == "cursor":
            r = _merge_json(project_dir / ".cursor" / "mcp.json", "mcpServers", server, std)
        elif h == "copilot":
            r = _merge_json(project_dir / ".vscode" / "mcp.json", "servers", server,
                            {"type": "stdio", **std})
        elif h == "devin":
            r = _merge_json(project_dir / ".devin" / "mcp_config.json", "mcpServers", server, std)
        elif h == "opencode":
            r = _merge_json(project_dir / "opencode.json", "mcp", server,
                            {"type": "local", "command": [cmd, *args], "environment": env,
                             "enabled": True})
        elif h == "codex":
            r = _codex_toml(home / ".codex" / "config.toml", server, cmd, args, env)
        else:
            r = {"status": "erro", "detalhe": f"harness desconhecido: {h}"}
        r["harness"] = h
        out.append(r)
    return out


def install_skill(project_dir: Path, harnesses: list[str]) -> list[str]:
    """Copia a skill /learn (SKILL.md) para os harnesses que leem skills do projeto."""
    src = resources.files("teammem") / "skills" / "learn" / "SKILL.md"
    targets = []
    if "claude" in harnesses:
        targets.append(project_dir / ".claude" / "skills" / "learn" / "SKILL.md")
    if "devin" in harnesses:
        targets.append(project_dir / ".devin" / "skills" / "learn" / "SKILL.md")
    written = []
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        with resources.as_file(src) as f:
            shutil.copyfile(f, t)
        written.append(str(t))
    return written


def ensure_claude_import(project_dir: Path) -> bool:
    """Garante que o CLAUDE.md importe o AGENTS.md (fonte única de instruções)."""
    f = project_dir / "CLAUDE.md"
    old = f.read_text(encoding="utf-8") if f.exists() else ""
    if "@AGENTS.md" in old:
        return False
    f.write_text("@AGENTS.md\n" + ("\n" + old if old else ""), encoding="utf-8")
    return True
