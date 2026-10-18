# Guia rápido — modo particular

## 1. Criar o acervo (uma vez)

```bash
uvx --from git+https://github.com/gregori/teammem teammem init minha-memoria --profile personal
cd minha-memoria
git add -A && git commit -m "acervo inicial"
gh repo create minha-memoria --private --source . --push
```

No GitHub do acervo, em **Settings → Actions → General**:
- *Workflow permissions*: **Read and write**
- marque **Allow GitHub Actions to create and approve pull requests**

E em **Settings → Variables → Actions**, crie `TEAMMEM_SOURCE` =
`git+https://github.com/gregori/teammem` (ou uma versão fixa quando houver release).

O workflow `teammem-curate` roda diariamente e a cada push na `inbox`:
- itens `auto` (projeto/global; gotcha, pattern, anti-pattern) vão **direto para a main** como `provisional`;
- itens `humano` (decision, convention, team/org, pinned, duplicatas, URLs) viram **PR**;
- itens `bloqueado` ficam na inbox e aparecem no log.

## 2. Configurar os projetos

```bash
export TEAMMEM_REPO=git@github.com:gregori/minha-memoria.git
cd ~/projetos/algum-projeto
uvx --from git+https://github.com/gregori/teammem teammem install \
  --source git+https://github.com/gregori/teammem \
  --harness claude codex opencode cursor
```

O que é escrito:

| Harness | Arquivo |
|---|---|
| Claude Code | `.mcp.json`, `.claude/skills/learn/SKILL.md`, `CLAUDE.md` com `@AGENTS.md` |
| Cursor | `.cursor/mcp.json` |
| OpenCode | `opencode.json` |
| Codex | `~/.codex/config.toml` (nível de usuário) |
| Todos | bloco `teammem` no `AGENTS.md` |

> O MCP descobre o projeto pela pasta raiz do git onde o harness o inicia. No
> Codex, a config é global: se o projeto não for detectado, a memória fica
> com escopo `global` ou você informa `project` no `propose`.

## 3. Usar

No harness, basta trabalhar: o AGENTS.md instrui o agente a chamar `search`
antes de decisões e `propose` ao aprender algo. Para registrar explicitamente,
use `/learn` (Claude Code) ou peça "registra esse aprendizado na memória".

Pela CLI:

```bash
teammem search "retry http"
teammem list
teammem show <id>
teammem review --list        # o que está na inbox e como o curador classificou
teammem stale                # memórias com review_by vencido
teammem doctor
```

## 4. Atualizar o bloco do AGENTS.md

Quando uma memória `pinned` entrar ou sair da main:

```bash
teammem agents-md
```
