# teammem

Memória compartilhada **multi-projeto e multi-harness** para agentes de IA de código.
Vai além de uma skill: em vez de só estilo e procedimentos, compartilha **aprendizados**
(decisões, armadilhas, convenções, padrões) com **proveniência, curadoria e envelhecimento**.

- **Fonte da verdade:** um repositório git de markdown (o *acervo*). Sem banco, sem servidor.
- **Acesso:** servidor MCP local (stdio) — o mesmo para Claude Code, Codex, OpenCode,
  Cursor, Devin CLI e GitHub Copilot (VS Code).
- **Canal estático:** bloco gerado no `AGENTS.md` com as memórias críticas (*pinned*).
- **Escrita:** `propose` grava na branch `inbox`; todos leem na hora como *pendente*.
- **Curadoria:** `review` promove da inbox para a `main` — automática (particular) ou
  por PR com merge humano (trabalho).

## Documentação

| Documento | Para quê |
|---|---|
| [docs/PLANO-IMPLEMENTACAO.md](docs/PLANO-IMPLEMENTACAO.md) | Plano completo, incluindo a adaptação para o ambiente corporativo |
| [docs/SPEC.md](docs/SPEC.md) | Contrato: formato das memórias, tools do MCP, fluxo de curadoria |
| [docs/USO.md](docs/USO.md) | Guia rápido do modo particular |

## Início rápido (modo particular)

| Quando | O quê |
|---|---|
| Uma vez na vida | Criar o acervo (`init`) |
| **Uma vez por máquina** | Instalar nos harnesses (`install --user`) |
| Por projeto, só se houver memórias críticas próprias | `agents-md` |

```bash
alias tm='uvx --from git+https://github.com/gregori/teammem teammem'

# 1. Acervo (repositório de dados privado). Se o repositório já existir,
#    clone-o e rode `tm init . --profile personal` dentro dele.
tm init minha-memoria --profile personal
cd minha-memoria && git add -A && git commit -m "acervo inicial"
gh repo create minha-memoria --private --source . --push

# 2. Uma vez por máquina: MCP, skill /learn e instruções globais em todos os harnesses
tm install --user --repo git@github.com:gregori/minha-memoria.git --name pessoal \
  --source git+https://github.com/gregori/teammem

# 3. Confira
tm doctor --repo git@github.com:gregori/minha-memoria.git --name pessoal
```

Detalhes, caminhos por harness e o modo por projeto: [docs/USO.md](docs/USO.md).

## Desenvolvimento

```bash
uv venv && uv pip install -e '.[dev]'
pytest
```

Licença: MIT.
