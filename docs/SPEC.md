# Especificação teammem (v1)

Este documento é o **contrato** compartilhado entre implementações. A versão
particular (este repositório) e a versão corporativa podem divergir no código,
mas devem respeitar esta spec. Assim, memórias migram entre acervos copiando o
arquivo, e skills e agentes falam com qualquer acervo.

## 1. Acervo (repositório de dados)

```
<acervo>/
├── .teammem.yaml          # política de curadoria
├── global/  team/  org/   # memórias de escopo amplo
├── project/<projeto>/     # memórias de um projeto (slug do nome da pasta git)
└── (branch inbox) inbox/  # propostas pendentes
```

- **`main`**: só recebe memórias promovidas. Pode (e no trabalho deve) ser protegida.
- **`inbox`**: branch sem proteção. Cada proposta é **um arquivo novo**
  `inbox/<id>.md`, de modo que pushes concorrentes nunca conflitam.
- O nome do arquivo é o `id` da memória.

## 2. Formato da memória

Markdown com frontmatter YAML:

```markdown
---
id: 2026-10-18-rodrigo-cliente-http-ja-faz-retry
title: Cliente HTTP interno já faz retry
type: gotcha
scope: project
project: api-pedidos
author: rodrigo
source: https://git.empresa/api-pedidos/pull/123
confidence: high
status: validated
pinned: false
tags: [http, retry]
created: '2026-10-18'
last_validated: '2026-10-20'
review_by: '2027-04-16'
supersedes: []
schema_version: 1
---

Não envolva chamadas em `tenacity`: os retries se multiplicam e estouram o rate
limit do parceiro. Configure o retry no próprio cliente (`HttpClient(retries=…)`).
```

| Campo | Obrigatório | Valores / regra |
|---|---|---|
| `id` | sim | `AAAA-MM-DD-<autor>-<slug-do-título>`; igual ao nome do arquivo |
| `title` | sim | uma linha |
| `type` | sim | `decision` · `gotcha` · `convention` · `pattern` · `anti-pattern` |
| `scope` | sim | `global` · `team` · `org` · `project` |
| `project` | se `scope=project` | nome do projeto |
| `author` | recomendado | quem propôs |
| `source` | recomendado | PR, issue, arquivo ou sessão de origem |
| `confidence` | não | `low` · `medium` (padrão) · `high` |
| `status` | não | `provisional` (padrão) · `validated` (revisada por humano) |
| `pinned` | não | `true` = vai para o AGENTS.md (ver §5) |
| `tags` | não | lista |
| `created` | sim | data ISO |
| `last_validated` | não | data da última revisão humana |
| `review_by` | não | data após a qual a memória é considerada *stale* |
| `supersedes` | não | ids que esta memória substitui |
| `schema_version` | sim | `1` |

**Corpo:** curto (2–6 linhas), factual e acionável: o que acontece, por quê e o que fazer.

### Destino na main

- `scope=project` → `project/<slug(project)>/<id>.md`
- demais → `<scope>/<id>.md`

## 3. Contrato do MCP

Transporte: stdio. Nome do servidor sugerido: `teammem-<acervo>`.

| Tool | Parâmetros | Retorno |
|---|---|---|
| `list_index` | `scope?`, `project?`, `include_inbox=true` | lista de `{id, title, type, scope, project, status, pinned}`; `status="pendente"` para itens da inbox |
| `read` | `ids: list[str]` | memórias completas (frontmatter + `body` + `origin` + `aviso` quando não revisada) |
| `search` | `query`, `scope?`, `type?`, `project?`, `limit=10` | memórias com `trecho` e `relevancia`, ordenadas |
| `propose` | `title`, `body`, `type`, `scope="project"`, `project?`, `source?`, `confidence?`, `tags?`, `pinned?` | `{status: publicada \| na_fila \| recusada, id, path, similares?, alertas?, motivos?}` |
| `review_pending` | — | propostas com `nivel` (`auto` · `humano` · `bloqueado`), `motivos` e `similares` |
| `promote` | `ids`, `mode="pr"\|"direct"` | resultado da promoção (branch/PR ou commit na main) |

Regras de visibilidade:
- Memórias `scope=project` só aparecem para o próprio projeto (o projeto atual é
  a pasta raiz do git onde o harness iniciou o MCP, ou `TEAMMEM_PROJECT`).
- Itens da inbox aparecem como **pendentes**, com peso menor no ranking.
- `provisional` aparece com peso menor que `validated`.

Regras de segurança (obrigatórias em qualquer implementação):
- `propose` **recusa** segredos e texto com cara de instrução ao agente.
- Comandos de shell e URLs não bloqueiam, mas forçam revisão humana.
- As instruções do servidor dizem ao agente que memória é **dado, não instrução**.
- `promote` só deve ser chamado após aprovação explícita do usuário.

## 4. Curadoria

### Níveis

| Nível | Critério (política padrão) | Destino |
|---|---|---|
| `bloqueado` | segredo ou prompt injection | não pode ser promovida |
| `humano` | escopo fora de `auto_scopes`, tipo fora de `auto_types`, `pinned`, `supersedes`, possível duplicata, URL/comando | PR com merge humano |
| `auto` | todo o resto | particular: direto na main como `provisional`; trabalho: entra no lote marcada como baixo risco |

### Política (`.teammem.yaml`)

```yaml
auto_scopes: [project]
auto_types: [gotcha, pattern, anti-pattern]
duplicate_threshold: 0.6   # similaridade Jaccard de tokens
inbox_ttl_days: 90         # proposta não promovida expira
pinned_max: 15             # teto de memórias críticas no AGENTS.md
```

### Promoção

1. Cria a branch `promote/<timestamp>` **a partir da main**.
2. Copia só os itens aprovados para o destino (§2), com `status=validated` e
   `last_validated=hoje` (modo `pr`), ou `status=provisional` (modo `direct`).
3. Faz push e abre o PR (`gh` ou `glab`, se disponíveis).
4. Depois do merge, o `gc` remove da inbox os ids que já estão na main e as
   propostas expiradas.

Itens que já estão em alguma branch `promote/*` não reaparecem como pendentes.

## 5. Canal estático (arquivos de instrução)

Um bloco delimitado por `<!-- teammem:<acervo>:start -->` e
`<!-- teammem:<acervo>:end -->`. O nome do acervo nos marcadores permite que
acervos diferentes (ex.: particular e trabalho) convivam no mesmo arquivo.

Dois níveis:

| Nível | Onde | Conteúdo |
|---|---|---|
| Usuário | arquivos de instrução globais de cada harness (ex.: `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`) | instrução de uso das tools (`search` antes de decidir, `propose` ao aprender) + `pinned` de escopo `global`/`team`/`org` |
| Projeto | `AGENTS.md` do repositório | só as `pinned` daquele projeto; sem `pinned` próprias, não há bloco |

O total de `pinned` em cada bloco respeita `pinned_max`.

**Critério de `pinned`** (todos verdadeiros):
1. **Sem gatilho:** o agente erraria antes de ter motivo para buscar.
2. **Custo alto:** o erro é destrutivo, silencioso ou caro em tempo.
3. **Abrangência:** vale para boa parte das tarefas.

O `CLAUDE.md` importa o `AGENTS.md` (`@AGENTS.md`), mantendo uma fonte única.

## 6. Versionamento

- `schema_version` no frontmatter; mudanças incompatíveis incrementam a versão
  e vêm com um comando de migração.
- Os adaptadores dos harnesses devem fixar a versão do pacote (`teammem==X.Y.Z`).
