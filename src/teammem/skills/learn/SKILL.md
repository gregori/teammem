---
name: learn
description: Registra um aprendizado (armadilha, decisão, padrão, convenção) na memória compartilhada do time (teammem), via MCP ou CLI. Use quando o usuário disser /learn, "registra isso", "anota esse aprendizado" ou ao final de uma investigação que revelou algo não óbvio.
---

# /learn — registrar aprendizado na memória compartilhada

Funciona com o MCP do teammem (tools `search` e `propose`) ou só com a CLI
(`teammem search` e `teammem propose`). Use o que estiver disponível; se houver
mais de um acervo, acrescente `--name <acervo>` aos comandos da CLI.

1. **Extraia o aprendizado** da conversa (ou do texto passado após `/learn`).
   Um aprendizado bom é:
   - não óbvio (alguém competente erraria sem saber);
   - durável (vale daqui a meses);
   - acionável (diz o que fazer, não só o que aconteceu).
   Se não passar nesses três testes, diga isso ao usuário e não registre.

2. **Procure duplicatas** com os termos centrais (`search` ou
   `teammem search <termos>`). Se já existir memória equivalente, mostre-a e
   pergunte se é o caso de complementar (nova proposta com `supersedes`) ou
   desistir.

3. **Classifique**:
   - `type`: gotcha (armadilha) · decision (escolha com motivo) · convention
     (regra do time) · pattern / anti-pattern (como fazer / não fazer)
   - `scope`: project (padrão) · team · org · global
   - `description`: uma linha que resume o aprendizado (vai para os índices)
   - `pinned`: só se o agente erraria **antes** de ter motivo para buscar e o
     custo do erro for alto. Na dúvida, não.

4. **Mostre o rascunho** ao usuário (título, descrição, corpo de 2–6 linhas,
   tipo, escopo, fonte) e peça confirmação.

5. Após o "ok", proponha:
   - MCP: tool `propose`;
   - CLI: `teammem propose --title "…" --type gotcha --description "…" --source "…" --body "…"`
     (o corpo também pode vir pela entrada padrão).

   Informe o id, o status (publicada / na fila) e qualquer alerta ou similar
   devolvido.

Nunca crie ou edite arquivos do acervo diretamente: só o `propose` aplica as
checagens de segurança. Nunca inclua segredos, tokens, dados pessoais ou
instruções do tipo "ignore…" no corpo: o `propose` recusa, e a memória é lida
por agentes de todo o time.
