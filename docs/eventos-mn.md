# Eventos do MN que mexem no estoque

Catálogo completo, lido do banco do ERP em 20/09/2026: **57 eventos**, marcados
`+` quando entram no estoque e `−` quando saem.

Cada linha tem os dois códigos. O parâmetro `EVENTO` da API recebe o **interno**;
o código do ERP é o que aparece na tela. Eles colidem — interno `12` é devolução
de varejo, código `12` é recebimento de transferência.

**`eventos/Eventos_InfluenciaEstoque` devolve exatamente os 20 eventos `+`** —
conferido interno a interno contra esta lista. Nenhum de saída, apesar do nome
prometer "influência de estoque" e venda influenciar estoque. Para o catálogo
completo use `eventos/ListaEventosPorTipo`.

---

## Os 51 eventos com movimento em 2026

Lido do banco em 20/09. **Esta lista substitui uma primeira que veio errada** —
e a versão errada já tinha me feito escrever duas conclusões falsas neste mesmo
documento. Ficam registradas abaixo, porque o erro é instrutivo.

Os maiores, que é onde mora o significado:

| interno | descrição | movimentos |
|---:|---|---:|
| 30 | VENDA CUPOM FISCAL | 6.141 |
| 14 | REMESSA DE CONSIGNAÇÃO | 3.433 |
| 19 | ACERTO DE CONSIGNAÇÃO | 2.818 |
| **4** | **TRANSFERÊNCIA DE ESTOQUE PA** | **2.013** |
| 25 | FATURAMENTO E-COMMERCE | 1.542 |
| **106** | **VENDAS ENTRE FILIAIS** | **1.186** |
| 12 | DEVOLUÇÃO DE VENDA VAREJO | 1.179 |
| **105** | **RECEBIMENTO DE COMPRA P.A (LOJAS)** | **922** |
| 109 | REMESSA SIMBOLICA ELENATIMES SP | 585 |
| 108 | FATURAMENTO ATACADO ELENATIMES ES | 575 |
| 114 | RETORNO P.A ELENATIMES (VAREJO) | 516 |
| 7 | RETORNO DE PRODUCAO | 504 |
| 107 | RETORNO P.A ELENATIMES (ATACADO) | 309 |
| **0** | **ENTRADA SIMPLES DE ESTOQUE PRODUTO** | **312** |
| 115 | RECEBIMENTO ELENATIMES (ATACADO) | 306 |
| 102 | REMESSA M.P ELENATIMES ES - SP | 295 |
| 104 | RECEBIMENTO DE COMPRA ELENATIMES ES | 292 |
| 23 | DEVOLUÇÃO DE VENDA E-COMMERCE | 245 |
| 56 | VENDA NFCE | 232 |
| 10 | VENDA | 192 |
| 202 | VENDA OUTLET | 173 |
| 48 | RETORNO DE CONSERTO FORNECEDORES | 151 |
| 6 | REMESSA PARA INDUSTRIALIZAÇÃO | 120 |
| 1 | ENTRADA SIMPLES DE MATÉRIA PRIMA | 104 |
| **2** | **SAÍDA SIMPLES PA** | **98** |
| 27 | DEVOLUÇÃO TROCA/CUPOM E-COMMERCE | 98 |
| 15 | REMESSA PARA CONSERTO FORNECEDOR | 70 |
| 103 | RECEBIMENTO DE COMPRA P.A | 54 |

Cauda longa: 21 (40), 32 (40), 16 (37), 52 (34), 38 (26), 121 (17), 9 (12),
17/18 (11 e 1), 207 (11), 22 (11), 34 (10), 110 (9), 204 (7), 28 (6), 8 e 11 (4),
50 (4), 117 (4), 206 (3), 14-bis/5 (2), 3 (1), 201 (1), 203 (1), **208 (1)**.

### O que essa correção derruba

**Errado: "nenhum evento de ajuste manual rodou em 2026."** Rodou muito.
`TRANSFERÊNCIA DE ESTOQUE PA` tem **2.013 movimentos**, o quarto maior do ano;
`ENTRADA SIMPLES DE ESTOQUE PRODUTO` tem 312 e `SAÍDA SIMPLES PA`, 98. Isso
**reabre o item 2 da D13**: existe peça mudando de saldo por fora de compra,
produção e nota. Enquanto não se souber o que passa por aí, o Estoque inicial
derivado não fecha sozinho.

**Errado: "`106 VENDAS ENTRE FILIAIS` é cadastro morto."** Tem 1.186 movimentos
— e é, literalmente, o nome que o negócio usa para descrever a remessa da Elena
para as lojas.

**Continua valendo, por outro motivo:** o `208 TRANSFERÊNCIA MATRIZ PARA LOJAS
( VENDA )` foi usado **uma vez** no ano inteiro. O nome perfeito segue não sendo
uso.

### Os candidatos, agora

| interno | descrição | mov. | por que |
|---:|---|---:|---|
| 106 | VENDAS ENTRE FILIAIS | 1.186 | o termo que o negócio usa; lado da saída |
| 105 | RECEBIMENTO DE COMPRA P.A (LOJAS) | 922 | único com (LOJAS); lado da entrada |
| 4 | TRANSFERÊNCIA DE ESTOQUE PA | 2.013 | transferência direta, sem nota |
| 114 | RETORNO P.A ELENATIMES (VAREJO) | 516 | o caminho de volta, subtrai da loja |
| 0 | ENTRADA SIMPLES DE ESTOQUE PRODUTO | 312 | ajuste manual de entrada |

`106` (saída) com `105` (entrada) formam o par mais coerente: a Elena "vende
entre filiais", a loja "recebe compra P.A (LOJAS)". A diferença de 264
movimentos no ano cabe no que a Elena manda para outros destinos que não as
duas lojas.

Só a chamada decide. Nenhum nome, nenhuma contagem — a chamada.

## Venda de varejo

| interno | código | descrição | no sellout |
|---:|---|---|---|
| 10 | `09` | VENDA | **sim** |
| 30 | `00027` | VENDA CUPOM FISCAL | **sim** |
| 204 | `00206` | VENDA CUPOM FISCAL - MÚLTIPLO VENDEDOR | **sim** |
| 28 | `00025` | VENDA VAREJO LOJA | **sim** (6 mov. no ano) |
| 56 | `23` | VENDA NFCE | **sim** (232 mov. no ano) |
| 9 | `08` | FATURAMENTO DE PEDIDO DE VENDA | sim (12 mov.) |
| 202 | `00203` | VENDA OUTLET | incluído; a filial é que filtra |
| 201 | `00201` | FATURAMENTO DE BAZAR | incluído; a filial é que filtra |
| 12 | `11` | DEVOLUÇÃO DE VENDA VAREJO | **sim** (subtrai) |
| 24 | `102` | RETORNO DE PRODUTO COM FINANCEIRO COM ESTOQUE | não — zero movimento |

Os três primeiros vieram do estudo do Projeto Conversão. **`VENDA VAREJO LOJA` e
`VENDA NFCE` nunca foram testados** — e a validação de 19/09 deixou faltando 2
peças em JARDINS e 1 no SITE. É o primeiro lugar a procurar.

## E-commerce

| interno | código | descrição | no sellout |
|---:|---|---|---|
| 25 | `00003` | FATURAMENTO E-COMMERCE | **sim** |
| 120 | `00129` | FATURAMENTO E-COMMERCE 00040 | **não** — zero movimento |
| 23 | `00002` | DEVOLUÇÃO DE VENDA E-COMMERCE | **sim** (subtrai) |
| 27 | `00004` | DEVOLUÇÃO TROCA/CUPOM E-COMMERCE | **sim** (subtrai) |

O `00129` cita uma segunda filial de e-commerce, a `00040`, mas não teve nenhum
movimento em 2026. **A única filial de e-commerce ativa é a `00044`**,
confirmado pelo negócio.

## Entrada de estoque na loja — o Estoque inicial (D13)

Ver **Os candidatos, agora**, acima. Resumo: `106 VENDAS ENTRE FILIAIS` (saída,
1.186) com `105 RECEBIMENTO DE COMPRA P.A (LOJAS)` (entrada, 922) é o par mais
coerente, e `4 TRANSFERÊNCIA DE ESTOQUE PA` (2.013) é o curinga — transferência
direta, sem nota, e o quarto maior evento do ano.

## Atacado — fora do sellout

| interno | código | descrição |
|---:|---|---|
| 108 | `00110` | FATURAMENTO ATACADO ELENATIMES ES |
| 113 | `00118` | FATURAMENTO ELENATIMES ES |
| 115 | `00123` | RECEBIMENTO ELENATIMES (ATACADO) |
| 107 | `00109` | RETORNO P.A ELENATIMES (ATACADO) |
| 207 | `00210` | DEVOLUÇÃO PARA ELENATIMES |
| 116 | `00125` | DEVOLUÇÃO OIRID X EGREY |

## Ajuste manual — a entrada que não passa por transferência

Mexem no saldo sem vir de compra, produção ou nota. **E rodam muito:**

| interno | código | descrição | lado | movimentos |
|---:|---|---|---|---:|
| 4 | `05` | TRANSFERÊNCIA DE ESTOQUE PA | − | **2.013** |
| 0 | `01` | ENTRADA SIMPLES DE ESTOQUE PRODUTO | + | **312** |
| 2 | `03` | SAÍDA SIMPLES PA | − | 98 |
| 121 | `00130` | TRANSFERÊNCIA DE ESTOQUE IMPORTAÇÃO | − | 17 |
| 38 | `00037` | ENTRADA IMPORTAÇÃO | + | 26 |
| 110 | — | TRANSFERÊNCIA DE SALDOS EGREY | ? | 9 |
| 206 | — | SAÍDA SIMPLES DIVERSOS | − | 3 |

Este é **o ponto em aberto mais pesado da D13**. Se parte dessas 2.013
transferências de estoque for Elena → loja, ou loja → loja, o Estoque inicial
não sai só da nota fiscal. Medir quanto disso toca IGUATEMI e EGREY JDS numa
semana é o próximo teste, não uma curiosidade.

## Matéria-prima, produção, conserto e consignação — fora

Não tocam peça acabada de loja.

| interno | código | descrição | lado |
|---:|---|---|---|
| 1 | `02` | ENTRADA SIMPLES DE MATÉRIA PRIMA | + |
| 3 | `04` | SAÍDA SIMPLES M.P. | − |
| 16 | `15` | RECEBIMENTO DE COMPRA M.P. | + |
| 40 | `1000` | BAIXA DE MATERIA PRIMA | − |
| 42 | `1010` | FATURAMENTO DE MATERIA PRIMA | − |
| 111 | `00116` | RECEBIMENTO DE TRANSFERENCIA MP | + |
| 112 | `00117` | REMESSA PARA BENEFICIAMENTO MP | − |
| 117 | `00126` | RETORNO M.P. ELENATIMES SP - ES | − |
| 6 | `18` | REMESSA PARA INDUSTRIALIZAÇÃO | − |
| 20 | `00015` | RETORNO DE INSUMOS | + |
| 8 | `19` | RETORNO DE CONSERTO | − |
| 15 | `21` | REMESSA PARA CONSERTO FORNECEDOR | − |
| 48 | `00049` | RETORNO DE CONSERTO FORNECEDORES | + |
| 50 | `00053` | ENTRADA CONSERTO | + |
| 52 | `00055` | RETORNO DE DEMONSTRAÇÃO | + |
| 14 | `13` | REMESSA DE CONSIGNAÇÃO | − |
| 19 | `14` | ACERTO DE CONSIGNAÇÃO | − |
| 22 | `22` | RETORNO DE CONSIGNAÇÃO SEM VENDA | − |
| 34 | `E01` | ENTRADA DE CONSIGNACAO | + |
| 36 | `S01` | ACERTO CONSIGNAÇÃO | − |
| 17 | `16` | DEVOLUÇÃO PARA FORNECEDOR P.A. | − |
| 18 | `17` | DEVOLUÇÃO PARA FORNECEDORES | − |

---

## A lição do catálogo

A extração estava rodando com **3 dos 10** eventos de venda de varejo, escolhidos
num estudo que olhava outra coisa. Ela não dava erro, não vinha vazia, e bateu ao
centavo no IGUATEMI — porque naquela loja, naquela semana, os outros sete não
tiveram movimento.

Uma lista de eventos incompleta é indistinguível de uma completa até o dia em que
alguém usa o evento que falta. Por isso o catálogo vira documento, e por isso a
tabela em `mn.EVENTOS` carrega os dois códigos: para que a próxima divergência
apareça sozinha.
