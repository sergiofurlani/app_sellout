# Roteiro

Quatro etapas. Cada uma entrega algo utilizável e **nenhuma quebra o caminho
atual** — a rodada por planilha continua funcionando até você decidir desligá-la.

---

## Etapa 0 · Ponto de retorno ✅

Antes de qualquer mudança estrutural.

- Tag `v1.0` no commit do processo por planilha, funcionando e conferido
- Documentação: arquitetura, decisões, operação
- Procedimento de volta documentado em `operacao.md`

Voltar a este momento: `git checkout v1.0` e um deploy. Um comando.

## Etapa 1 · Banco e ingestão

- Postgres no mesmo projeto Railway
- Migrações versionadas — o banco muda por arquivo no repositório, nunca na mão
- Adaptador de upload: as mesmas planilhas viram snapshot no banco
- Carga do histórico: as 237 colunas de sellout viram linhas
- Congelamento do saldo de abertura a partir do Estoque inicial de hoje (D10)

Ao final desta etapa o banco existe e é alimentado, mas **nada muda para você** —
a rodada semanal segue igual. É de propósito: se algo estiver errado, dá para
comparar banco contra planilha antes de confiar.

## Etapa 2 · A tela

- Tabela hierárquica: produto → expandir → cores
- Filtros por coleção, divisão, departamento e linha comercial
- Sellout de qualquer período, sem coluna nova
- Exportação para Excel no formato de hoje
- Telas de edição do que é nosso: linha comercial e movimentos de entrada

Aqui a planilha vira saída, não fonte.

## Etapa 3 · Ligar no ERP

- Adaptador de leitura direta, substituindo o upload
- Agendamento: o app busca sozinho, você só confere e fecha a semana
- A tela de conferência continua — a validação de layout e as pendências
  seguem valendo, só muda de onde o dado vem

## Etapa 4 · Aplicativo

- PWA: instala na tela inicial, abre como aplicativo
- Ajuste da tabela para telas pequenas
- Consulta offline do último fechamento

---

## Pontos em aberto

**Saldo de abertura por cor.** O valor de hoje existe por produto. Ao descer para
cor, três saídas:

1. Ratear o saldo do produto entre as cores na proporção de estoque + vendas
   atuais. Dá histórico imediato, mas o número nasce estimado.
2. Marcar a data-base e contar o sellout por cor só dali em diante. O sellout por
   produto continua com o histórico completo e intacto.
3. Ratear, mas marcar essas linhas como estimadas na tela, e elas vão ficando
   exatas conforme as semanas passam.

**Recomendo a 3.** Você vê número desde o primeiro dia, sabe quais são
aproximados, e a aproximação some sozinha. A 1 esconde a incerteza e a 2 deixa a
tela vazia por meses.

**Acesso ao ERP.** Falta saber qual é o ERP e que tipo de acesso existe — banco
direto com usuário de leitura, ou API. Isso define a Etapa 3 e nada antes dela.

**Cor na aba Produção.** É a única origem que traz o nome da cor sem o código.
Casar por nome funciona hoje, mas é frágil. Se der para incluir o código no
export, resolve na fonte.

**Segurança.** Hoje o app está aberto na internet, sem senha. Sem banco isso é
pouco relevante — quem achasse a URL veria uma tela de upload vazia. Com o banco
guardando estoque, preço e venda da Egrey, passa a ser exposição real. A Etapa 1
precisa incluir pelo menos uma senha, mesmo sendo você o único usuário.
