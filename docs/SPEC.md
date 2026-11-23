# Especificação teammem (v1)

Este documento é o **contrato** compartilhado entre implementações. A versão
particular (este repositório) e a versão corporativa podem divergir no código,
mas devem respeitar esta spec. Assim, memórias migram entre acervos copiando o
arquivo, e skills e agentes falam com qualquer acervo.

O acervo é um **bundle [OKF v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)**
(Open Knowledge Format). O OKF padroniza o **formato**; curadoria, inbox,
identidade de projeto e checagens de segurança continuam sendo do teammem.

## 1. Acervo (repositório de dados)

```
<acervo>/
├── index.md               # gerado; único com frontmatter: okf_version: "0.2"
├── log.md                 # gerado; histórico de promoções, mais recente primeiro
├── .teammem.yaml          # política de curadoria
├── global/  team/  org/   # memórias de escopo amplo (+ index.md gerado)
├── project/<slug>/        # memórias de um projeto (+ index.md gerado)
├── projects/<slug>.md     # notas de projeto: identidade (remotes, aliases)
└── (branch inbox) inbox/  # propostas pendentes
```

- **`main`**: só recebe memórias promovidas. Pode (e no trabalho deve) ser protegida.
- **`inbox`**: branch sem proteção. Cada proposta é **um arquivo novo**
  `inbox/<id>.md`, de modo que pushes concorrentes nunca conflitam.
- O nome do arquivo é o `id` da memória. A identidade OKF do conceito é o
  caminho sem `.md` (ex.: `project/api-pedidos/2026-10-18-rodrigo-…`).
- **Conformidade:** todo `.md` não reservado tem frontmatter com `type`;
  `index.md` não tem frontmatter, exceto o da raiz (`okf_version`); `log.md` usa
  cabeçalhos `## AAAA-MM-DD`. `teammem validate` verifica.

## 2. Formato da memória

Conceito OKF: markdown com frontmatter YAML. Os campos do OKF vêm primeiro; os
demais são extensões do teammem (o OKF exige que consumidores as preservem).

```markdown
---
type: gotcha
title: Cliente HTTP interno já faz retry
description: Não envolva chamadas em tenacity.
tags: [http, retry]
status: stable
sources:
- resource: https://git.empresa/api-pedidos/pull/123
verified:
- by: human:rodrigo
  at: '2026-10-20T00:00:00+00:00'
stale_after: '2027-04-16T00:00:00+00:00'
id: 2026-10-18-rodrigo-cliente-http-ja-faz-retry
scope: project
project: api-pedidos
author: rodrigo
confidence: high
pinned: false
created: '2026-10-18'
schema_version: 1
---

Não envolva chamadas em `tenacity`: os retries se multiplicam e estouram o rate
limit do parceiro. Configure o retry no próprio cliente (`HttpClient(retries=…)`).
```

| Campo | Origem | Obrigatório | Valores / regra |
|---|---|---|---|
| `type` | OKF | sim | `decision` · `gotcha` · `convention` · `pattern` · `anti-pattern` (notas de projeto: `project`) |
| `title` | OKF | sim | uma linha |
| `description` | OKF | recomendado | uma linha; vai para os `index.md`. Padrão: primeira frase do corpo |
| `tags` | OKF | não | lista |
| `status` | OKF | não | `draft` (proposta na inbox) · `stable` (na main) · `deprecated`. Ausente = `stable` |
| `sources` | OKF | recomendado | lista de `{resource: <PR, issue, arquivo ou sessão>}` |
| `verified` | OKF | não | lista de `{by, at}`. `by: human:<pessoa>` = revisada por humano |
| `stale_after` | OKF | não | datetime ISO 8601 com offset; a partir dela a memória está *stale* |
| `id` | teammem | sim | `AAAA-MM-DD-<autor>-<slug-do-título>`; igual ao nome do arquivo |
| `scope` | teammem | sim | `global` · `team` · `org` · `project` |
| `project` | teammem | se `scope=project` | identidade (slug) do projeto (§3) |
| `author` | teammem | recomendado | quem propôs |
| `confidence` | teammem | não | `low` · `medium` (padrão) · `high` |
| `pinned` | teammem | não | `true` = vai para o canal estático (§7) |
| `created` | teammem | sim | data ISO |
| `supersedes` | teammem | não | ids que esta memória substitui |
| `schema_version` | teammem | sim | `1` |

**Estado de curadoria (derivado, não gravado):** `pendente` (está na inbox),
`validated` (tem `verified` com ator `human:`) ou `provisional` (na main, sem
revisão humana).

**Corpo:** curto (2–6 linhas), factual e acionável: o que acontece, por quê e o que fazer.

### Destino na main

- `scope=project` → `project/<slug(project)>/<id>.md`
- demais → `<scope>/<id>.md`

## 3. Identidade de projeto

A identidade de um projeto é um **slug** (até 96 caracteres). Toda comparação
usa o slug dos dois lados (`API Pedidos`, `api-pedidos` e `api_pedidos` são o
mesmo projeto).

**Nota de projeto** (`projects/<slug>.md`, na main, editada por PR):

```markdown
---
type: project
title: API de pedidos
description: Serviço de pedidos do e-commerce
remotes:
- github.com/zup/api-pedidos
aliases: [pedidos]
---

Texto livre sobre o projeto.
```

`remotes` guarda URLs **normalizadas**: `host/caminho`, em minúsculas, sem
esquema, credenciais, porta ou `.git` (`git@github.com:Zup/API.git` →
`github.com/zup/api`).

**Resolução do projeto atual**, nesta ordem:

1. override explícito (`--project` ou `TEAMMEM_PROJECT`);
2. nota cujo `remotes` contém o `origin` normalizado do repositório atual;
3. nota cujo slug ou `aliases` coincide com o nome da pasta git;
4. slug do `origin` normalizado (`github.com/zup/api` → `github-com-zup-api`);
5. slug do nome da pasta, só quando o repositório não tem `origin`;
6. nenhum: `propose` com `scope=project` é recusado com explicação.

Sem nota, a identidade já é estável entre clones e worktrees, porque vem do
`origin`. A nota acrescenta um nome legível, aliases e a lista de repositórios
do projeto. Na **leitura**, um projeto com nota aceita memórias gravadas com o
slug da nota, de qualquer `remotes` ou de qualquer `aliases`: criar a nota
depois não esconde o que já foi registrado. Na **escrita**, usa-se o slug da
nota. `teammem project` mostra a resolução e sugere a nota.

## 4. Índices e log (arquivos reservados do OKF)

São **gerados** a partir das memórias e notas, de forma determinística, na
promoção (`promote`) e por `teammem index`. Nunca são editados à mão: um
conflito de merge neles se resolve rodando `teammem index` de novo (no
`log.md`, mantenha as entradas dos dois lados).

| Arquivo | Conteúdo |
|---|---|
| `index.md` (raiz) | `okf_version: "0.2"`, regras de leitura (memória é dado; só a main é norma), links para os escopos, projetos, notas e log |
| `<escopo>/index.md` | entradas agrupadas por tipo: `* [Título](/caminho.md) - description`, com marcas *crítica*, *não revisada*, *obsoleta* |
| `project/index.md`, `project/<slug>/index.md` | projetos com memórias; o do projeto aponta para a nota |
| `projects/index.md` | notas de projeto com os remotes |
| `log.md` | `## AAAA-MM-DD` seguido de `* **Promoção**: [Título](/caminho.md) (tipo, escopo/projeto)` |

Os índices permitem que um agente leia o acervo **sem MCP**, navegando a
partir do `index.md` raiz (progressive disclosure).

## 5. Interfaces: MCP e CLI

Há duas interfaces equivalentes. O **MCP é opcional**: com o acervo em OKF, a
leitura pode ser feita direto nos arquivos, e busca e escrita pela CLI. A
escrita sempre passa por `propose` (MCP ou CLI), que aplica as checagens de
segurança; agentes nunca escrevem arquivos do acervo diretamente.

**MCP** — transporte stdio, servidor `teammem-<acervo>`:

| Tool | Parâmetros | Retorno |
|---|---|---|
| `list_index` | `scope?`, `project?`, `include_inbox=true` | lista de `{id, title, type, scope, project, status, pinned}`; `status="pendente"` para itens da inbox |
| `read` | `ids: list[str]` | memórias completas (frontmatter + `body` + `origin` + `aviso` quando não revisada) |
| `search` | `query`, `scope?`, `type?`, `project?`, `limit=10` | memórias com `trecho` e `relevancia`, ordenadas |
| `propose` | `title`, `body`, `type`, `scope="project"`, `project?`, `source?`, `confidence?`, `tags?`, `pinned?`, `description?` | `{status: publicada \| na_fila \| recusada, id, path, similares?, alertas?, motivos?}` |
| `where` | — | projeto atual (como foi resolvido) e caminho do `index.md` local |
| `review_pending` | — | propostas com `nivel` (`auto` · `humano` · `bloqueado`), `motivos` e `similares` |
| `promote` | `ids`, `mode="pr"\|"direct"` | resultado da promoção (branch/PR ou commit na main) |

**CLI** — mesmos contratos, saída JSON: `teammem list | show | search | propose
| where | project`. Sem `--repo`, a CLI usa o único acervo já clonado em
`~/.teammem/` (ou o escolhido com `--name`).

**Arquivos** — o clone local da `main` (`~/.teammem/<acervo>/main`), a partir
do `index.md` raiz. Itens da inbox ficam em `~/.teammem/<acervo>/inbox/inbox/`
e são pistas não revisadas.

Regras de visibilidade:
- Memórias `scope=project` só aparecem para o próprio projeto (§3).
- Itens da inbox aparecem como **pendentes**, com peso menor no ranking.
- `provisional` (sem `verified` humano) aparece com peso menor que `validated`.

Regras de segurança (obrigatórias em qualquer implementação):
- `propose` **recusa** segredos e texto com cara de instrução ao agente.
- Comandos de shell e URLs não bloqueiam, mas forçam revisão humana.
- As instruções do servidor, o bloco de instruções (§7) e o `index.md` raiz
  dizem ao agente que memória é **dado, não instrução**.
- `promote` só deve ser chamado após aprovação explícita do usuário.

## 6. Curadoria

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
2. Copia só os itens aprovados para o destino (§2), com `status: stable`. No
   modo `pr`, acrescenta `verified: {by: human:<curador>, at: agora}`; no modo
   `direct`, não (a memória fica `provisional`).
3. Regenera os `index.md` e acrescenta as entradas ao `log.md` (§4), no mesmo commit.
4. Faz push e abre o PR (`gh` ou `glab`, se disponíveis).
5. Depois do merge, o `gc` remove da inbox os ids que já estão na main e as
   propostas expiradas.

Itens que já estão em alguma branch `promote/*` não reaparecem como pendentes.

## 7. Canal estático (arquivos de instrução)

Um bloco delimitado por `<!-- teammem:<acervo>:start -->` e
`<!-- teammem:<acervo>:end -->`. O nome do acervo nos marcadores permite que
acervos diferentes (ex.: particular e trabalho) convivam no mesmo arquivo.

Dois níveis:

| Nível | Onde | Conteúdo |
|---|---|---|
| Usuário | arquivos de instrução globais de cada harness (ex.: `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`) | instrução de uso (`search` antes de decidir, `propose` ao aprender), na variante MCP ou na variante sem MCP (caminho do clone + comandos da CLI) + `pinned` de escopo `global`/`team`/`org` |
| Projeto | `AGENTS.md` do repositório | só as `pinned` daquele projeto; sem `pinned` próprias, não há bloco |

O total de `pinned` em cada bloco respeita `pinned_max`.

**Critério de `pinned`** (todos verdadeiros):
1. **Sem gatilho:** o agente erraria antes de ter motivo para buscar.
2. **Custo alto:** o erro é destrutivo, silencioso ou caro em tempo.
3. **Abrangência:** vale para boa parte das tarefas.

O `CLAUDE.md` importa o `AGENTS.md` (`@AGENTS.md`), mantendo uma fonte única.

## 8. Versionamento

- `schema_version` no frontmatter; mudanças incompatíveis incrementam a versão
  e vêm com um comando de migração.
- O formato base acompanha o OKF declarado em `okf_version` no `index.md` raiz.
- Os adaptadores dos harnesses devem fixar a versão do pacote (`teammem==X.Y.Z`).
