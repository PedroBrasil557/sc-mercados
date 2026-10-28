# Lançamento na Google Play: checklist

Exigências conferidas nas páginas oficiais em 28/10/2026. Conta: **pessoal** (a empresa ainda não tem CNPJ).

## Conta e prazos

- [ ] Criar a conta de desenvolvedor pessoal (US$ 25, cartão de crédito). Verificar identidade, e-mail e telefone.
- [ ] Conferir a verificação de desenvolvedor Android (obrigatória no Brasil desde 30/09/2026) em Configurações > Conta de desenvolvedor.
- [ ] Usar Play App Signing e guardar a chave de upload em local seguro: sem ela, não dá para registrar o pacote.
- [ ] **Teste fechado obrigatório (conta pessoal):** 12 testadores inscritos por 14 dias seguidos. Quem sai e volta reinicia a contagem. Recrutar desde o primeiro dia (famílias do teste de usabilidade).
- [ ] Pedir acesso à produção pelo Painel depois do teste fechado. Prazo total realista: 3 a 4 semanas.
- [ ] Quando houver CNPJ: avaliar migrar para conta de organização (D-U-N-S gratuito, até 30 dias).

## Técnico

- [x] Alvo API 36 (Android 16): o Expo SDK 58 já usa por padrão.
- [x] AAB (`eas build -p android --profile production`) e 64 bits: padrão do Expo.
- [ ] Páginas de memória de 16 KB (obrigatório a partir de 01/02/2027): conferir com `zipalign -c -P 16` no AAB.
- [ ] Remover `ACCESS_FINE_LOCATION`, que o expo-location adiciona por padrão. Só localização aproximada, em primeiro plano.
- [ ] Desligar `RECORD_AUDIO` do expo-camera (`recordAudioAndroid: false`).
- [ ] `POST_NOTIFICATIONS` só a partir de uma ação da pessoa (tela 28, pedido em duas etapas).
- [ ] Atualizações remotas (EAS Update) só para correções de JS e textos. Nunca para mudar permissões, dados coletados ou o propósito do app.

## Políticas e formulários

- [ ] Política de privacidade em página web pública (não pode ser PDF), com link no Console e dentro do app. Passar pelo advogado. Precisa dizer que os dados ficam guardados nos EUA (Supabase us-east-2, Render Ohio): transferência internacional, LGPD art. 33.
- [ ] Exclusão de conta: dentro do app (Perfil > Apagar tudo, já desenhado) **e** por link web, sem exigir o app. Apagar de verdade, não congelar. *API pronta: `DELETE /v1/eu` (28/10/2026); falta a tela e a página web.*
- [ ] Segurança dos dados:
  - Informações financeiras > Histórico de compras: itens e preços do cupom, enviados ao servidor.
  - Atividade no app: eventos de uso, só com consentimento.
  - Informações pessoais: e-mail e/ou telefone da conta (opcional).
  - IDs do dispositivo: token de notificação.
  - Localização aproximada: só se for enviada ao servidor. Hoje só sugere o bairro no aparelho, então não precisa declarar.
  - Não declarar CPF: ele é apagado no aparelho e nunca pode passar por log, URL ou relatório de falha.
- [ ] Classificação de conteúdo (IARC) e público-alvo: 18+.
- [ ] Declarações: sem anúncios; não é app do governo; sem recursos financeiros.
- [ ] Acesso ao app para o revisor: instruções de como entrar sem conta.

## Riscos de política e mitigação

- **WebView da Sefaz/SC:**
  - Carregar só URLs `https://` dos domínios da Sefaz/SC vindas do QR, sem `addJavascriptInterface` com conteúdo arbitrário.
  - Não usar brasão nem logo do governo.
  - Na descrição: "Não somos afiliados à Secretaria da Fazenda de SC".
- **Preços coletados de sites:**
  - Respeitar robots.txt e termos (o coletor já faz isso).
  - Nenhum logo de supermercado na ficha ou no ícone.
  - Data e fonte de cada preço visíveis (R6).
- **Analytics:** nenhum SDK envia nada antes do consentimento.

## Ficha da loja

- [ ] Ícone 512×512 PNG com alfa (a partir do componente "Ícone do app" no Figma).
- [ ] Gráfico de destaque 1024×500.
- [ ] Capturas de tela: de 4 a 8, em 1080×1920 (9:16). As telas do Figma são 2,16:1, acima do limite de 2:1, então é preciso criar artes próprias para a loja.
- [ ] Nome até 30 caracteres; descrição curta até 80; sem "melhor", "#1", "grátis" nem "promoção" no título.

## Depois do lançamento

- [ ] Android vitals: falhas percebidas ≤ 1,09% e ANR ≤ 0,47%. Relatório de falhas desde o primeiro dia.
