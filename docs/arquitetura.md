# Arquitetura

## Onde estamos (v1.0)

Processador sem estado: entram duas planilhas, saem três arquivos.

```
sellout geral.xlsx ──┐
                     ├──▶ [analisar] ──▶ tela de conferência ──▶ [processar] ──▶ 3 arquivos
Sellout Clássicos ───┘
```

A planilha é, ao mesmo tempo, o banco de dados e o relatório. As abas Estoque,
Vendas, Producao, Preco e Produtos são exports do ERP coladas na mesma pasta de
trabalho; as abas Masculino e Feminino são o relatório, com o histórico crescendo
em colunas para a direita.

**O que funciona bem:** a conferência antes de gravar, a detecção de mudança de
layout na origem, o relatório de pendências.

**O que não funciona:** a saída de uma semana é a entrada da seguinte, então erro
não se corrige — se acumula. E o grão é o produto, não a cor.

### Módulos

```
sellout/core/cores.py      normalização e casamento de nomes de cor
sellout/core/leitura.py    leitura das abas de origem, detecção de colunas
sellout/core/divisao.py    divisão de um código entre linhas pelo vermelho (D1)
sellout/core/motor.py      análise e processamento da rodada
sellout/core/relatorio.py  relatório de conferência
sellout/web/               app FastAPI, três telas
sellout/cli.py             execução pelo terminal
```

## Para onde vamos (v2)

```
ERP (banco/API) ──▶ [ingestão] ──▶ Postgres ──▶ [consulta] ──▶ tela por cor (PWA)
                         ▲                          │
   upload .xlsx ─────────┘                          └──▶ exportação .xlsx
```

A ingestão é uma camada com dois adaptadores para a mesma interface: upload de
planilha e leitura direta do ERP. O resto do sistema não sabe de onde o dado
veio. É o que permite começar pelo upload e trocar depois sem refazer nada.

### Modelo de dados

Dimensões, estáveis:

| tabela | chave | campos |
|---|---|---|
| `produto` | codigo | descricao, divisao, departamento, grupo, marca, grade, colecao, **linha** |
| `cor` | codigo_cor | nome |
| `produto_cor` | codigo + codigo_cor | — |
| `filial` | codigo | nome |

O código de cor é global: 68 códigos, nenhum com dois nomes. `0002` é PRETO em
qualquer produto. Vira tabela de dimensão de verdade, não texto repetido.
Tamanhos são 21 valores.

Fatos, um retrato por semana:

| tabela | grão |
|---|---|
| `snapshot` | id, data, origem (upload/erp), quem rodou |
| `estoque` | snapshot + codigo + codigo_cor + tamanho + filial → qtd |
| `venda` | snapshot + codigo + codigo_cor + tamanho + filial → qtd, valor |
| `producao` | snapshot + codigo + codigo_cor + tamanho → qtd |
| `preco` | snapshot + codigo + codigo_cor + tamanho → preco |

Saldo, o dado que é nosso (D10):

| tabela | grão |
|---|---|
| `saldo_abertura` | codigo + codigo_cor + data_base → qtd, origem |
| `movimento` | data + codigo + codigo_cor → tipo, qtd, observação |

**Estoque inicial** deixa de ser fórmula e passa a ser
`saldo_abertura + Σ movimentos até a data`. O sellout de qualquer período vira
consulta, não coluna: `vendas acumuladas ÷ estoque inicial`.

Consequência prática: aquelas 237 colunas viram uma linha por semana na tabela
de snapshots. Comparar 08/09 com 23/08 passa a ser um filtro.

### A tela

Uma tabela hierárquica: linha do produto, com o total; clicou, abre as linhas de
cor. Filtros por coleção, divisão, departamento e linha comercial. A mesma tela
serve no celular e instala como aplicativo (PWA) — sem app store, mesma base de
código.

O Excel continua saindo por um botão, no formato de hoje, enquanto a tela ganha
confiança.

## O que não muda

As regras de negócio dos documentos de decisão continuam valendo, com uma
exceção: a divisão pelo texto em vermelho (D1) perde a razão de existir quando o
grão passa a ser a cor. O código fica no repositório, marcado como legado, para
a migração poder ser conferida contra ele.
