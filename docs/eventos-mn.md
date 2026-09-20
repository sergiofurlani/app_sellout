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

## Os 21 eventos com movimento em 2026

Lido do banco em 20/09. **Metade do catálogo é cadastro antigo.** Um evento que
existe e nunca é usado não é candidato a nada — e foi contra essa lista que a
melhor hipótese do dia anterior morreu.

| interno | descrição | movimentos |
|---:|---|---:|
| 30 | VENDA CUPOM FISCAL | 6.141 |
| 25 | FATURAMENTO E-COMMERCE | 1.542 |
| 12 | DEVOLUÇÃO DE VENDA VAREJO | 1.179 |
| **105** | **RECEBIMENTO DE COMPRA P.A (LOJAS)** | **922** |
| 108 | FATURAMENTO ATACADO ELENATIMES ES | 575 |
| 7 | RETORNO DE PRODUCAO | 501 |
| 104 | RECEBIMENTO DE COMPRA ELENATIMES ES | 290 |
| 23 | DEVOLUÇÃO DE VENDA E-COMMERCE | 245 |
| 56 | VENDA NFCE | 232 |
| 10 | VENDA | 192 |
| 202 | VENDA OUTLET | 173 |
| 27 | DEVOLUÇÃO TROCA/CUPOM E-COMMERCE | 98 |
| 103 | RECEBIMENTO DE COMPRA P.A | 54 |
| 16 | RECEBIMENTO DE COMPRA M.P. | 36 |
| 19 | ACERTO DE CONSIGNAÇÃO | 18 |
| 9 | FATURAMENTO DE PEDIDO DE VENDA | 12 |
| 34 | ENTRADA DE CONSIGNACAO | 7 |
| 204 | VENDA CUPOM FISCAL - MÚLTIPLO VENDEDOR | 7 |
| 28 | VENDA VAREJO LOJA | 6 |
| 17 | DEVOLUÇÃO PARA FORNECEDOR P.A. | 1 |
| 201 | FATURAMENTO DE BAZAR | 1 |

### Três conclusões imediatas

**O `208 CD-04 TRANSFERÊNCIA MATRIZ PARA LOJAS ( VENDA )` não tem movimento em
2026.** Nem o `13`, nem o `106 VENDAS ENTRE FILIAIS`, nem o `203`. Eram a
hipótese mais bonita do projeto — o nome dizia literalmente o que o negócio
descrevia — e são cadastro morto. Nome bom não é uso.

**O que entra peça na loja é o `105 RECEBIMENTO DE COMPRA P.A (LOJAS)`, com 922
movimentos** — o maior evento de entrada do ano, e o primeiro palpite lá do
começo. A Elena fatura (`108`, 575) e a loja recebe (`105`, 922); a produção
entra na Elena pelo `7 RETORNO DE PRODUCAO` (501).

**Nenhum evento de ajuste manual foi usado em 2026.** `ENTRADA SIMPLES DE
ESTOQUE PRODUTO`, `SAÍDA SIMPLES PA` e `TRANSFERÊNCIA DE ESTOQUE PA` estão
zerados. Isso fecha o item 2 da D13: não há entrada de loja por fora, então o
Estoque inicial derivado pode fechar sozinho.

E `FATURAMENTO E-COMMERCE 00040` também está zerado — **a única filial de
e-commerce ativa é a `00044`**, confirmado pelo negócio.

## Venda de varejo

| interno | código | descrição | no sellout |
|---:|---|---|---|
| 10 | `09` | VENDA | **sim** |
| 30 | `00027` | VENDA CUPOM FISCAL | **sim** |
| 204 | `00206` | VENDA CUPOM FISCAL - MÚLTIPLO VENDEDOR | **sim** |
| 28 | `00025` | VENDA VAREJO LOJA | **a testar** |
| 56 | `23` | VENDA NFCE | **a testar** |
| 9 | `08` | FATURAMENTO DE PEDIDO DE VENDA | a testar |
| 202 | `00203` | VENDA OUTLET | filial fora do sellout |
| 201 | `00201` | FATURAMENTO DE BAZAR | filial fora do sellout |
| 12 | `11` | DEVOLUÇÃO DE VENDA VAREJO | **sim** (subtrai) |
| 24 | `102` | RETORNO DE PRODUTO COM FINANCEIRO COM ESTOQUE | a testar |

Os três primeiros vieram do estudo do Projeto Conversão. **`VENDA VAREJO LOJA` e
`VENDA NFCE` nunca foram testados** — e a validação de 19/09 deixou faltando 2
peças em JARDINS e 1 no SITE. É o primeiro lugar a procurar.

## E-commerce

| interno | código | descrição | no sellout |
|---:|---|---|---|
| 25 | `00003` | FATURAMENTO E-COMMERCE | **sim** |
| 120 | `00129` | FATURAMENTO E-COMMERCE 00040 | **a testar** |
| 23 | `00002` | DEVOLUÇÃO DE VENDA E-COMMERCE | **sim** (subtrai) |
| 27 | `00004` | DEVOLUÇÃO TROCA/CUPOM E-COMMERCE | **sim** (subtrai) |

O `00129` cita uma segunda filial de e-commerce, a `00040`. Na semana validada o
SITE (`00044`) fechou com uma peça de diferença, então a `00040` ou não vendeu ou
é justamente a peça que falta.

## Entrada de estoque na loja — o Estoque inicial (D13)

O ciclo, pelos eventos que de fato rodam:

| interno | código | descrição | movimentos | papel |
|---:|---|---|---:|---|
| 7 | — | RETORNO DE PRODUCAO | 501 | produção entra na Elena |
| 108 | `00110` | FATURAMENTO ATACADO ELENATIMES ES | 575 | Elena fatura |
| **105** | `00107` | **RECEBIMENTO DE COMPRA P.A (LOJAS)** | **922** | **a loja recebe** |
| 104 | `00106` | RECEBIMENTO DE COMPRA ELENATIMES ES | 290 | recebimento na Elena |
| 103 | `00105` | RECEBIMENTO DE COMPRA P.A | 54 | genérico |

`105` é o maior evento de entrada do ano e o único cujo nome diz **(LOJAS)**.
É o candidato a Estoque inicial.

**Descartados por não terem movimento em 2026**, apesar dos nomes perfeitos:
`208 CD-04 TRANSFERÊNCIA MATRIZ PARA LOJAS ( VENDA )`, `13 RECEBIMENTO DE
TRANSFERENCIA MATRIZ`, `106 VENDAS ENTRE FILIAIS`, `203 VENDAS ENTRE FILIAIS
( CONF )`, `209 EC-55`, `114 RETORNO P.A ELENATIMES (VAREJO)`.

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

Estes mexem no saldo sem vir de compra, produção ou transferência. São o
"outro caminho" que a D13 listava como a validar: o que entrar por aqui **não**
aparece na transferência da Elena e continua invisível.

| interno | código | descrição | lado |
|---:|---|---|---|
| 0 | `01` | ENTRADA SIMPLES DE ESTOQUE PRODUTO | + |
| 2 | `03` | SAÍDA SIMPLES PA | − |
| 4 | `05` | TRANSFERÊNCIA DE ESTOQUE PA | − |
| 121 | `00130` | TRANSFERÊNCIA DE ESTOQUE IMPORTAÇÃO | − |
| 103 | `00105` | RECEBIMENTO DE COMPRA P.A | + |
| 119 | `00128` | ENTRADA DE DEVOLUÇÃO DE COMPRA P.A | + |
| 38 | `00037` | ENTRADA IMPORTAÇÃO | + |

Vale medir quanto passa por aí numa semana. Se for zero, o Estoque inicial
derivado fecha sozinho; se não for, precisa de lançamento à parte.

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
