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

O par que mais se encaixa na descrição do negócio, "a Elena manda para as lojas
por um evento de venda entre filiais":

| interno | código | descrição | lado |
|---:|---|---|---|
| **208** | `CD-04` | **TRANSFERÊNCIA MATRIZ PARA LOJAS ( VENDA )** | saída |
| **13** | `12` | **RECEBIMENTO DE TRANSFERENCIA MATRIZ** | entrada |

Saída da matriz, entrada na loja, e o `( VENDA )` no nome explica por que o
negócio chama aquilo de venda entre filiais. "Matriz" aparece nos dois.

Outros candidatos, a descartar pela chamada:

| interno | código | descrição | lado |
|---:|---|---|---|
| 106 | `00108` | VENDAS ENTRE FILIAIS | saída |
| 203 | `00205` | VENDAS ENTRE FILIAIS ( CONF ) | saída |
| 105 | `00107` | RECEBIMENTO DE COMPRA P.A (LOJAS) | entrada |
| 104 | `00106` | RECEBIMENTO DE COMPRA ELENATIMES ES | entrada |

E o caminho de volta, loja → matriz, que **subtrai** do estoque da loja:

| interno | código | descrição | lado |
|---:|---|---|---|
| 209 | `EC-55` | TRANSFERÊNCIA LOJA PARA MATRIZ (DEVOLUÇÃO) | saída |
| 114 | `00120` | RETORNO P.A ELENATIMES (VAREJO) | saída |

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
