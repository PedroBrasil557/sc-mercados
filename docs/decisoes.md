# Decisões

A especificação completa do produto (regras R1–R16, telas, métricas, modelo de dados, agentes) está no documento "Quanto Fica — Especificação do produto". O design de alta fidelidade e os tokens estão no Figma "Quanto Fica — App MVP".

| Data | Decisão | Motivo |
|---|---|---|
| 28/10/2026 | O centro do app é a **lista de compras da casa**, compartilhada | Comparar preço é necessidade mensal; a lista gera hábito diário e semanal |
| 28/10/2026 | Lançamento para **famílias** de Blumenau, Android primeiro | Maior economia em reais e mais motivo para voltar |
| 28/10/2026 | **App nativo com Expo SDK 58** (React Native, TypeScript); a página web do convite sai do mesmo código | Câmera para cupom e código de barras; um só código para Android, iPhone e web |
| 28/10/2026 | **Backend em Python** (FastAPI) com **PostgreSQL**; Supabase e Fly.io na região São Paulo | Coletores e agentes já são Python; dados no Brasil evitam transferência internacional (LGPD art. 33) |
| 28/10/2026 | **5 agentes** (Catalogador, Leitor de Encartes, Casador de Cupom, Vigia, Auditor) em `claude-opus-5-5` | O agente propõe e as regras decidem; meta de 99% de precisão no que é publicado automaticamente |
| 28/10/2026 | **Sem fotos de produto no lançamento**: miniatura tipográfica com o emblema da categoria | Fotos de terceiros exigem autorização (Lei 9.610/98, art. 29); o crédito não basta. Fotos só com licença (Syndigo/marcas) |
| 28/10/2026 | Lançamento com **preço de varejo**; preço de sócio numa versão seguinte | Simplicidade e comparação justa |
| 28/10/2026 | **Conta pessoal** na Play Store por enquanto | Ainda não há CNPJ; exige 12 testadores por 14 dias no teste fechado |
| 28/10/2026 | Valores em **centavos** (inteiros); datas em UTC; EAN sempre com 14 dígitos | Sem erro de arredondamento; comparação de EAN com e sem zeros |
| 28/10/2026 | Observação de preço e operação da lista são **imutáveis** (gatilho no banco) | Histórico para ofertas reais (R9) e sincronização sem perder edições (R15) |
