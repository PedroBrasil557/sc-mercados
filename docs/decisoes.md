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
| 28/10/2026 | **Identidade sem cadastro**: o aparelho recebe um token na primeira abertura; o banco guarda só o SHA-256. Família entra na casa por **código de convite** (8 caracteres, 48 h, até 10 entradas) | Começar a usar sem criar conta (R16). Vazamento da tabela não dá acesso a nenhuma lista |
| 28/10/2026 | Lista de outra casa responde **404**, não 403 | Não revela que a lista existe |
| 28/10/2026 | **Limite de tentativas por IP** no cadastro (20/h) e no uso de convite (10 a cada 10 min) | Impede força bruta nos códigos de convite |
| 28/10/2026 | **Exclusão de conta** apaga o membro de verdade; as operações dele ficam na lista sem autoria; o último a sair leva a casa junto; se o dono sai, a casa passa para quem entrou primeiro | LGPD art. 18 e política da Google Play; a lista dos outros continua certa |
| 28/10/2026 | Lojas com preço on-line: endereço e coordenadas **oficiais da própria rede**. Bairros e redes sem site: **OpenStreetMap** (ODbL, atribuição na tela "Sobre"), marcadas como `openstreetmap` até confirmação | O OSM tinha o Angeloni Velha 2,7 km fora do lugar; a fonte oficial ganha |
| 28/10/2026 | O preço do site vale **só para a loja que atende o e-commerce** (Giassi Victor Konder, Angeloni Velha, Sam's; a Cooper tem preço por loja). As outras lojas da rede ficam sem preço do site | O preço da prateleira de outra loja pode ser diferente: não mostramos o que não sabemos |
| 28/10/2026 | Alertas do `npm audit` (zod 3 e deepmerge) **aceitos**: estão só na ferramenta de linha de comando do Expo, que lê a configuração local; nada disso vai para o app | A correção automática rebaixaria o Expo para o SDK 51. Rever a cada atualização do Expo |
| 28/10/2026 | React e React Native com **versão única** fixada em `overrides` na raiz | Duas cópias no monorepo quebram o app ("Invalid hook call") e o build nativo |
| 28/10/2026 | Nome do app: **SC Mercados**. Continua fazendo sentido na expansão por Santa Catarina; um nome nacional fica para quando sair do estado | Decisão do fundador. No código o projeto segue `quantofica` (nome interno, não aparece para ninguém) |
| 28/10/2026 | Robô de coleta se identifica como `SCMercadosColetor/0.1`, **sem URL** até existir o site | O endereço anterior (quantofica.app) não é nosso: apontar para ele enganaria os sites |
| 28/10/2026 | Coleta agendada por um **processo na própria Fly.io** (`relogio.py`), não no GitHub Actions | Não depende do código estar no GitHub; horário certo em Brasília; um dia ruim não derruba o relógio |
| 28/10/2026 | **RLS ligado em todas as tabelas**, sem política, e privilégios de `anon`/`authenticated` retirados | O Supabase publica o schema public numa API REST com chave pública; só a nossa API pode ler e gravar |
| 28/10/2026 | Migrações por executor próprio (`quantofica.banco.migrar`), registradas em `migracao_aplicada`, rodando no `release_command` da Fly.io | Publicar de novo nunca reaplica migração; o mesmo executor monta o banco dos testes |
