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

```bash
# 1. Crie o acervo (repositório de dados) e publique-o no GitHub (privado)
uvx --from git+https://github.com/gregori/teammem teammem init minha-memoria --profile personal
cd minha-memoria && git add -A && git commit -m "acervo inicial"
gh repo create minha-memoria --private --source . --push

# 2. Em cada projeto, configure os harnesses
cd ~/projetos/meu-projeto
uvx --from git+https://github.com/gregori/teammem teammem install \
    --repo git@github.com:gregori/minha-memoria.git \
    --source git+https://github.com/gregori/teammem \
    --harness claude codex opencode cursor

# 3. Confira
uvx --from git+https://github.com/gregori/teammem teammem doctor --repo git@github.com:gregori/minha-memoria.git
```

## Desenvolvimento

```bash
uv venv && uv pip install -e '.[dev]'
pytest
```

Licença: MIT.
