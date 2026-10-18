# Acervo de memórias (teammem)

Repositório de **dados** da memória compartilhada. A ferramenta que lê e escreve
aqui é o [teammem](https://github.com/gregori/teammem).

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `global/`, `team/`, `org/` | memórias de escopo amplo |
| `project/<nome>/` | memórias de um projeto |
| `.teammem.yaml` | política de curadoria |
| branch `inbox` → `inbox/` | propostas pendentes (escritas pelo `propose`) |

Cada memória é um `.md` com frontmatter (ver `docs/SPEC.md` no teammem).

## Fluxo

1. Agentes chamam `propose` → arquivo novo em `inbox/` na branch `inbox`.
2. Todos já leem a proposta como *pendente*.
3. `teammem review` promove os aprovados para a `main` (PR ou direto, conforme o perfil).
4. `teammem gc` limpa da inbox o que foi promovido ou expirou.
