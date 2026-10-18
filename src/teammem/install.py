"""Instalador multi-harness, em dois modos:

- **usuário** (`--user`, recomendado): uma vez por máquina. Config de MCP,
  skill /learn e instruções globais de cada harness. O MCP descobre o projeto
  pela pasta git onde o harness o inicia.
- **projeto**: escreve a config dentro do repositório do projeto (útil para
  versionar a config junto com o código).

Idempotente. Nunca sobrescreve um arquivo que não consegue interpretar (ex.:
JSON com comentários): nesse caso devolve o trecho para colar manualmente.

Caminhos e formatos (confirmados na documentação de cada ferramenta em out/2026;
revise a cada atualização):

| Harness  | MCP (projeto)            | MCP (usuário)                              | Instruções (usuário)              |
|----------|--------------------------|--------------------------------------------|-----------------------------------|
| Claude   | .mcp.json                | `claude mcp add-json -s user` (~/.claude.json) | ~/.claude/CLAUDE.md           |
| Cursor   | .cursor/mcp.json         | ~/.cursor/mcp.json                         | — (instruções do servidor MCP)    |
| Copilot  | .vscode/mcp.json         | <perfil VS Code>/User/mcp.json             | ~/.copilot/copilot-instructions.md|
| Devin    | .devin/mcp_config.json   | ~/.config/devin/mcp_config.json            | ~/.config/devin/AGENTS.md         |
| OpenCode | opencode.json            | ~/.config/opencode/opencode.json           | ~/.config/opencode/AGENTS.md      |
| Codex    | —                        | ~/.codex/config.toml                       | ~/.codex/AGENTS.md                |

Skills de usuário: ~/.claude/skills (Claude, OpenCode), ~/.agents/skills
(Codex, Devin, OpenCode) e a pasta de skills do Cursor.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

HARNESSES = ("claude", "cursor", "copilot", "devin", "opencode", "codex")


def server_cmd(source: str, repo: str, name: str) -> tuple[str, list[str], dict[str, str]]:
    """Comando que cada harness executa. `source` permite registry interno,
    git interno ou wheel local: ex. 'teammem==0.1.0', 'git+https://…', './dist/x.whl'."""
    args = ["--from", source, "teammem", "serve"]
    return "uvx", args, {"TEAMMEM_REPO": repo, "TEAMMEM_NAME": name}


# ------------------------------------------------------------------ caminhos
@dataclass
class UserPaths:
    home: Path
    system: str
    appdata: Path  # %APPDATA% no Windows, ~/.config ou ~/Library/Application Support

    @classmethod
    def detect(cls, home: Path | None = None, system: str | None = None) -> "UserPaths":
        home = home or Path.home()
        system = system or platform.system()
        if system == "Windows":
            appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        elif system == "Darwin":
            appdata = home / "Library" / "Application Support"
        else:
            appdata = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        return cls(home, system, appdata)

    @property
    def xdg(self) -> Path:
        """Ferramentas CLI (Devin, OpenCode) usam ~/.config mesmo no macOS."""
        if self.system == "Windows":
            return self.appdata
        return Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))

    @property
    def vscode_user(self) -> Path:
        return self.appdata / "Code" / "User"

    @property
    def cursor_skills(self) -> Path:
        base = self.appdata if self.system in ("Windows", "Darwin") else self.xdg
        return base / ("Cursor" if self.system in ("Windows", "Darwin") else "cursor") / "User" / "skills"


# ------------------------------------------------------------------ escrita
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


def _claude_user(server: str, entry: dict, paths: UserPaths, use_cli: bool) -> dict:
    """Claude Code guarda MCP de usuário em ~/.claude.json, um arquivo que o app
    reescreve. Por isso preferimos a CLI oficial; o arquivo é o fallback."""
    if use_cli and shutil.which("claude"):
        subprocess.run(["claude", "mcp", "remove", "--scope", "user", server],
                       capture_output=True, text=True)
        r = subprocess.run(
            ["claude", "mcp", "add-json", "--scope", "user", server,
             json.dumps({"type": "stdio", **entry})],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            return {"arquivo": "claude mcp (escopo user)", "status": "atualizado"}
    res = _merge_json(paths.home / ".claude.json", "mcpServers", server,
                      {"type": "stdio", **entry})
    if res["status"] == "atualizado":
        res["nota"] = "feche o Claude Code antes, ou ele pode sobrescrever ~/.claude.json"
    return res


def install(
    harnesses: list[str],
    *,
    repo: str,
    name: str,
    project_dir: Path | None = None,
    user: bool = False,
    source: str = "teammem",
    server: str | None = None,
    home: Path | None = None,
    system: str | None = None,
    use_claude_cli: bool = True,
) -> list[dict]:
    if not user and project_dir is None:
        raise ValueError("modo projeto exige project_dir")
    paths = UserPaths.detect(home, system)
    server = server or f"teammem-{name}"
    cmd, args, env = server_cmd(source, repo, name)
    std = {"command": cmd, "args": args, "env": env}
    opencode_entry = {"type": "local", "command": [cmd, *args], "environment": env,
                      "enabled": True}
    out = []
    for h in harnesses:
        if h == "claude":
            r = (_claude_user(server, std, paths, use_claude_cli) if user
                 else _merge_json(project_dir / ".mcp.json", "mcpServers", server, std))
        elif h == "cursor":
            base = paths.home if user else project_dir
            r = _merge_json(base / ".cursor" / "mcp.json", "mcpServers", server, std)
        elif h == "copilot":
            f = paths.vscode_user / "mcp.json" if user else project_dir / ".vscode" / "mcp.json"
            r = _merge_json(f, "servers", server, {"type": "stdio", **std})
        elif h == "devin":
            f = (paths.xdg / "devin" / "mcp_config.json" if user
                 else project_dir / ".devin" / "mcp_config.json")
            r = _merge_json(f, "mcpServers", server, std)
        elif h == "opencode":
            if user:
                base = paths.xdg / "opencode"
                f = base / "opencode.jsonc" if (base / "opencode.jsonc").exists() \
                    else base / "opencode.json"
            else:
                f = project_dir / "opencode.json"
            r = _merge_json(f, "mcp", server, opencode_entry)
        elif h == "codex":
            r = _codex_toml(paths.home / ".codex" / "config.toml", server, cmd, args, env)
        else:
            r = {"status": "erro", "detalhe": f"harness desconhecido: {h}"}
        r["harness"] = h
        out.append(r)
    return out


# ------------------------------------------------------------------ skills
def skill_targets(harnesses: list[str], *, project_dir: Path | None = None,
                  user: bool = False, paths: UserPaths | None = None) -> list[Path]:
    targets: list[Path] = []
    if user:
        paths = paths or UserPaths.detect()
        if {"claude", "opencode"} & set(harnesses):
            targets.append(paths.home / ".claude" / "skills")
        if {"codex", "devin", "opencode"} & set(harnesses):
            targets.append(paths.home / ".agents" / "skills")
        if "cursor" in harnesses:
            targets.append(paths.cursor_skills)
    else:
        if "claude" in harnesses:
            targets.append(project_dir / ".claude" / "skills")
        if "devin" in harnesses:
            targets.append(project_dir / ".devin" / "skills")
    return [t / "learn" / "SKILL.md" for t in targets]


def install_skill(harnesses: list[str], *, project_dir: Path | None = None,
                  user: bool = False, paths: UserPaths | None = None) -> list[str]:
    """Copia a skill /learn (SKILL.md) para onde cada harness procura skills."""
    src = resources.files("teammem") / "skills" / "learn" / "SKILL.md"
    written = []
    for t in skill_targets(harnesses, project_dir=project_dir, user=user, paths=paths):
        t.parent.mkdir(parents=True, exist_ok=True)
        with resources.as_file(src) as f:
            shutil.copyfile(f, t)
        written.append(str(t))
    return written


# ------------------------------------------------------------------ instruções
def instruction_targets(harnesses: list[str], paths: UserPaths) -> tuple[list[Path], list[str]]:
    """Arquivos de instrução global a atualizar, evitando duplicar o mesmo bloco
    para um harness que já lê o arquivo de outro. Retorna (arquivos, notas)."""
    hs = set(harnesses)
    files: list[Path] = []
    notes: list[str] = []
    claude_md = paths.home / ".claude" / "CLAUDE.md"
    if "claude" in hs:
        files.append(claude_md)
    if "codex" in hs:
        files.append(paths.home / ".codex" / "AGENTS.md")
    if "devin" in hs:
        if "claude" in hs:
            notes.append("Devin CLI lê ~/.claude/CLAUDE.md como regra global")
        else:
            files.append(paths.xdg / "devin" / "AGENTS.md")
    if "opencode" in hs:
        oc = paths.xdg / "opencode" / "AGENTS.md"
        # Criar o AGENTS.md global do OpenCode desliga o fallback para o CLAUDE.md
        if "claude" in hs and not oc.exists():
            notes.append("OpenCode lê ~/.claude/CLAUDE.md enquanto não houver "
                         "~/.config/opencode/AGENTS.md")
        else:
            files.append(oc)
    if "copilot" in hs:
        files.append(paths.home / ".copilot" / "copilot-instructions.md")
    if "cursor" in hs:
        notes.append("Cursor não tem arquivo de regras de usuário: a orientação de uso "
                     "chega pelas instruções do próprio servidor MCP")
    return files, notes


def ensure_claude_import(project_dir: Path) -> bool:
    """Garante que o CLAUDE.md do projeto importe o AGENTS.md (fonte única)."""
    f = project_dir / "CLAUDE.md"
    old = f.read_text(encoding="utf-8") if f.exists() else ""
    if "@AGENTS.md" in old:
        return False
    f.write_text("@AGENTS.md\n" + ("\n" + old if old else ""), encoding="utf-8")
    return True
