# Guia de uso — modo particular

A instalação tem três níveis, cada um feito uma única vez no seu escopo:

| Quando | O quê | Comando |
|---|---|---|
| **Uma vez na vida** | Criar o acervo (repositório de dados) | `teammem init` |
| **Uma vez por máquina** | MCP, skill `/learn` e instruções globais em todos os harnesses | `teammem install --user` |
| **Por projeto (opcional)** | Memórias críticas *daquele* projeto no AGENTS.md | `teammem agents-md` |

**Você não precisa instalar nada em cada projeto.** O MCP é configurado no nível
do usuário e descobre o projeto atual pela pasta git onde o harness o inicia.

Nos exemplos abaixo, `tm` é um atalho:

```bash
alias tm='uvx --from git+https://github.com/gregori/teammem teammem'
```

## 1. Criar o acervo (uma vez)

### Repositório ainda não existe

```bash
tm init minha-memoria --profile personal
cd minha-memoria && git add -A && git commit -m "acervo inicial"
gh repo create minha-memoria --private --source . --push
```

### Repositório já existe no GitHub

Clone e rode o `init` dentro dele. Ele não recria o `.git` e não sobrescreve
arquivos que já existem (seu README é mantido):

```bash
git clone git@github.com:gregori/minha-memoria.git && cd minha-memoria
tm init . --profile personal
git add -A && git commit -m "estrutura do acervo" && git push
```

### Configurar a curadoria automática

No GitHub do acervo:
- **Settings → Actions → General → Workflow permissions:** *Read and write* e
  *Allow GitHub Actions to create and approve pull requests*.
- **Settings → Secrets and variables → Actions → Variables:** crie
  `TEAMMEM_SOURCE` = `git+https://github.com/gregori/teammem`.

O workflow `teammem-curate` roda diariamente e a cada push na `inbox`:
- itens `auto` (escopo project/global; gotcha, pattern, anti-pattern) vão
  **direto para a main** como `provisional`;
- itens `humano` (decision, convention, team/org, pinned, duplicatas, URLs)
  viram **PR**;
- itens `bloqueado` ficam na inbox e aparecem no log.

## 2. Instalar na máquina (uma vez)

```bash
tm install --user \
  --repo git@github.com:gregori/minha-memoria.git \
  --name pessoal \
  --source git+https://github.com/gregori/teammem
```

Por padrão, configura todos os harnesses. Para escolher: `--harness claude codex opencode cursor`.

O que é escrito:

| Harness | MCP | Instruções globais | Skill `/learn` |
|---|---|---|---|
| Claude Code | `claude mcp add-json -s user` (ou `~/.claude.json`) | `~/.claude/CLAUDE.md` | `~/.claude/skills/` |
| Codex | `~/.codex/config.toml` | `~/.codex/AGENTS.md` | `~/.agents/skills/` |
| OpenCode | `~/.config/opencode/opencode.json` | lê `~/.claude/CLAUDE.md`¹ | lê `~/.claude/skills/` e `~/.agents/skills/` |
| Cursor | `~/.cursor/mcp.json` | — ² | pasta de skills do usuário do Cursor |
| Devin CLI | `~/.config/devin/mcp_config.json` | lê `~/.claude/CLAUDE.md`¹ | lê `~/.agents/skills/` |
| Copilot (VS Code) | `mcp.json` do perfil padrão do VS Code³ | `~/.copilot/copilot-instructions.md` | — |

1. Quando o Claude também é instalado, o bloco vai só no `~/.claude/CLAUDE.md`,
   que o OpenCode e o Devin já leem. Sem o Claude, cada um ganha o próprio
   `AGENTS.md` global.
2. O Cursor não tem arquivo de regras de usuário. A orientação de uso chega
   pelas instruções do próprio servidor MCP.
3. `~/.config/Code/User/mcp.json` (Linux), `~/Library/Application Support/Code/User/mcp.json`
   (macOS), `%APPDATA%\Code\User\mcp.json` (Windows). Se você usa um perfil não
   padrão do VS Code, abra **MCP: Open User Configuration** e cole o trecho.

O bloco de instruções tem marcadores com o nome do acervo
(`<!-- teammem:pessoal:start -->`). Assim, o acervo particular e o do trabalho
podem conviver no mesmo arquivo.

Rodar o comando de novo é seguro: ele é idempotente e não sobrescreve arquivos
que não consegue interpretar (JSON com comentários). Nesse caso, devolve o
trecho para colar manualmente.

Confira com:

```bash
tm doctor --repo git@github.com:gregori/minha-memoria.git
```

## 3. Por projeto (opcional)

Só é necessário quando o projeto tem memórias `pinned` próprias, ou seja,
críticas que o agente erraria antes de ter motivo para buscar:

```bash
cd ~/projetos/algum-projeto
tm agents-md --repo git@github.com:gregori/minha-memoria.git --name pessoal
```

O comando escreve no `AGENTS.md` do projeto só as `pinned` daquele projeto. Se
não houver nenhuma, ele não escreve nada (e remove um bloco antigo, se existir).

> **Quero versionar a config dentro do projeto?** Use `tm install` sem `--user`
> dentro do repositório. Ele grava `.mcp.json`, `.cursor/mcp.json`,
> `.vscode/mcp.json`, `.devin/mcp_config.json` e `opencode.json`, e o bloco
> completo no `AGENTS.md`. É útil quando quem clona o projeto não instalou o
> teammem na máquina.

## 4. Manter as instruções em dia

Quando uma memória `pinned` de escopo amplo (global/team/org) entrar ou sair
da main:

```bash
tm agents-md --user --repo git@github.com:gregori/minha-memoria.git --name pessoal
```

## 5. Usar

No harness, basta trabalhar: as instruções orientam o agente a chamar `search`
antes de decisões e `propose` ao aprender algo. Para registrar explicitamente,
use `/learn` ou peça "registra esse aprendizado na memória".

Se o harness iniciar o MCP fora de um repositório git, o projeto atual não é
detectado. Nesse caso, o `propose` com escopo `project` é recusado com uma
explicação: informe `project` ou use outro escopo.

Pela CLI. Depois do primeiro uso, a CLI acha sozinha o acervo clonado em
`~/.teammem/` (com mais de um acervo, use `--name`):

```bash
tm search "retry http"
tm list
tm show <id>
tm where                # projeto atual e caminhos do acervo local
tm project              # como o projeto foi identificado + nota sugerida
tm review --list        # o que está na inbox e como o curador classificou
tm stale                # memórias com stale_after vencido
tm doctor
```

## 6. Modo sem MCP

O acervo é um bundle [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md):
cada pasta tem um `index.md` gerado com links e descrições. Um agente consegue
navegar por ele só lendo arquivos, e a CLI cobre busca e escrita. Assim, o MCP
fica opcional:

```bash
uv tool install git+https://github.com/gregori/teammem   # `teammem` no PATH
teammem install --user --no-mcp --repo git@github.com:gregori/minha-memoria.git \
  --name pessoal --source git+https://github.com/gregori/teammem
```

O que muda em relação ao modo MCP:

| | Com MCP | Sem MCP |
|---|---|---|
| Ler | tools `list_index`, `read` | arquivos a partir de `~/.teammem/<acervo>/main/index.md` |
| Buscar | tool `search` | `teammem search` |
| Propor | tool `propose` | `teammem propose` (a skill `/learn` usa o que houver) |
| Sincronizar | automático, a cada chamada | a cada comando da CLI (`teammem sync` força) |
| Instruções globais | uso das tools | caminho do clone + comandos da CLI |

Nos dois modos, **toda escrita passa pelo `propose`**: só ele aplica as
checagens de segredo e de prompt injection. As instruções dizem ao agente para
nunca criar ou editar arquivos do acervo diretamente.

Sem `teammem` no PATH, as instruções usam `uvx --from <source> teammem`, que
funciona mas é mais lento.

## 7. Identidade do projeto

Por padrão, o projeto é o nome da pasta git (como na v1). Para que clones e
worktrees com outros nomes achem o mesmo projeto, crie uma **nota de projeto**
no acervo, por PR:

```bash
cd ~/projetos/api-pedidos
tm project          # mostra a resolução e a nota sugerida, com o remote
```

Salve a nota sugerida em `projects/<slug>.md` no seu clone do acervo,
complete `remotes` e `aliases` e abra um PR. A partir daí, o projeto é
encontrado pelo `origin`, independentemente do nome da pasta.

## 8. Migrar um acervo v1 para OKF

```bash
cd minha-memoria            # seu clone do acervo, na main
tm migrate .                # reescreve as memórias, cria notas de projeto e índices
tm validate .               # confere a conformidade OKF
git checkout -b migra-okf && git add -A && git commit -m "acervo: migra para OKF v0.2"
gh pr create --fill
```

Depois do merge, preencha `remotes` nas notas criadas. Se um PR de promoção
conflitar em `index.md`, rode `tm index .` no branch e faça o commit. No
`log.md`, mantenha as entradas dos dois lados.
