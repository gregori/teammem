---
name: learn
description: Registra um aprendizado (armadilha, decisão, padrão, convenção) na memória compartilhada do time via MCP teammem. Use quando o usuário disser /learn, "registra isso", "anota esse aprendizado" ou ao final de uma investigação que revelou algo não óbvio.
---

# /learn — registrar aprendizado na memória compartilhada

1. **Extraia o aprendizado** da conversa (ou do texto passado após `/learn`).
   Um aprendizado bom é:
   - não óbvio (alguém competente erraria sem saber);
   - durável (vale daqui a meses);
   - acionável (diz o que fazer, não só o que aconteceu).
   Se não passar nesses três testes, diga isso ao usuário e não registre.

2. **Procure duplicatas**: chame `search` com os termos centrais. Se já existir
   memória equivalente, mostre-a e pergunte se é o caso de complementar
   (nova proposta com `supersedes`) ou desistir.

3. **Classifique**:
   - `type`: gotcha (armadilha) · decision (escolha com motivo) · convention
     (regra do time) · pattern / anti-pattern (como fazer / não fazer)
   - `scope`: project (padrão) · team · org · global
   - `pinned`: só se o agente erraria **antes** de ter motivo para buscar e o
     custo do erro for alto. Na dúvida, não.

4. **Mostre o rascunho** ao usuário (título, corpo de 2–6 linhas, tipo, escopo,
   fonte) e peça confirmação.

5. Após o "ok", chame `propose`. Informe o id e o status (publicada / na fila)
   e qualquer alerta ou similar devolvido.

Nunca inclua segredos, tokens, dados pessoais ou instruções do tipo "ignore…"
no corpo: o `propose` recusa, e a memória é lida por agentes de todo o time.
