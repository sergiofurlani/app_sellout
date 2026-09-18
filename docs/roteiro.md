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

O ERP Millennium **só responde à rede da Egrey** — contêiner em nuvem não
alcança (ver `api-millennium.md`). Então não é o app que busca: é um coletor
rodando dentro da rede da Egrey que lê e empurra.

- Coletor na rede da Egrey, no mesmo molde do Projeto Conversão
- Endpoint autenticado no app para receber o que o coletor manda
- Agendamento no coletor; o app só recebe, valida e grava
- A tela de conferência continua igual — só muda de onde o dado vem

O formato enviado é o mesmo que a ingestão por upload consome, então nada da
Etapa 1 é desperdiçado. E o upload continua existindo como caminho de
emergência, para quando a rede ou o coletor falharem.

**Antes desta etapa é preciso descobrir os métodos de estoque, preço, produtos e
produção no `$metadata`** — o documento de origem só cobre venda.

## Etapa 4 · Aplicativo

- PWA: instala na tela inicial, abre como aplicativo
- Ajuste da tabela para telas pequenas
- Consulta offline do último fechamento

---

## Pontos em aberto

**Saldo de abertura por cor — provavelmente resolvido.** Ver D13: a entrada no
estoque das lojas é a movimentação da ELENA ES para elas, registrada por evento
de venda entre filiais, e isso está no MN com data, produto, cor e tamanho. Se a
soma dessas entradas reproduzir a coluna Estoque inicial da planilha, o problema
some — não há o que estimar.

Se não reproduzir, as três saídas antigas continuam valendo:

1. Ratear o saldo do produto entre as cores na proporção de estoque + vendas
   atuais. Dá histórico imediato, mas o número nasce estimado.
2. Marcar a data-base e contar o sellout por cor só dali em diante. O sellout por
   produto continua com o histórico completo e intacto.
3. Ratear, mas marcar essas linhas como estimadas na tela, e elas vão ficando
   exatas conforme as semanas passam.

**Recomendo a 3.** Você vê número desde o primeiro dia, sabe quais são
aproximados, e a aproximação some sozinha. A 1 esconde a incerteza e a 2 deixa a
tela vazia por meses.

**Métodos do ERP para estoque, preço, produtos e produção.** A exploração da API
Millennium cobriu venda; as outras quatro fontes ainda não têm método conhecido.
Estão no `$metadata`, que só é acessível de dentro da rede da Egrey.

**Qual filial é o Site.** A planilha separa Jardins, Iguatemi e Site; na amostra
da API nenhuma das filiais é obviamente o e-commerce. Sem isso a coluna Vendas
Site não é reproduzível pela API.

**Onde roda o coletor.** O Projeto Conversão já tem um processo na rede da Egrey.
Reaproveitar a mesma máquina e o mesmo agendamento é mais barato que montar outro.

**Cor na aba Produção.** É a única origem que traz o nome da cor sem o código.
Casar por nome funciona hoje, mas é frágil. Se der para incluir o código no
export, resolve na fonte.

**Segurança.** Hoje o app está aberto na internet, sem senha. Sem banco isso é
pouco relevante — quem achasse a URL veria uma tela de upload vazia. Com o banco
guardando estoque, preço e venda da Egrey, passa a ser exposição real. A Etapa 1
precisa incluir pelo menos uma senha, mesmo sendo você o único usuário.
