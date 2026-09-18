# API Millennium — o que vale para o sellout

Resumo da exploração feita em 13–17/09/2026 durante o Projeto Conversão, filtrado
pelo que interessa a este projeto, com as lacunas explicitadas. O documento
original é mais completo sobre venda e vendedor; aqui ficam o acesso, as
armadilhas que nos atingem e o que ainda falta descobrir.

## Acesso

```
Base:    http://egray.millenniumhosting.com.br:6017     (HTTP, não HTTPS)
Padrão:  /api/<modulo>/<grupo>/<metodo>?$format=json
Auth:    Authorization: Basic base64(usuario:senha)
```

O nome do método é sensível a maiúsculas no caminho. Credencial em variável de
ambiente, nunca em arquivo versionado. Se der 401 com credencial certa, testar o
header proprietário `WTS-Authorization` antes de concluir que a senha está errada.

## A restrição que define a arquitetura

**O ERP só responde à rede da Egrey.** Contêiner em nuvem não alcança — HTTPS é
resetado, HTTP fica em timeout. Verificado com Railway.

Consequência direta: **o app no Railway não pode buscar no ERP**. Ou a Millennium
libera o IP de saída da nuvem, ou o processo que lê o ERP roda dentro da rede da
Egrey e empurra o resultado. O Projeto Conversão seguiu o segundo caminho, e é o
que este projeto deve reaproveitar.

```
rede da Egrey                      nuvem
┌────────────────────┐            ┌──────────────────────┐
│ coletor            │  POST      │ app sellout          │
│  lê Millennium  ───┼───────────▶│  recebe e grava      │
│  agendado          │  autenticado│  Postgres            │
└────────────────────┘            └──────────────────────┘
```

O formato do que o coletor envia é o mesmo que a ingestão por upload já consome.
Só muda o transporte — nada do que for feito na Etapa 1 se perde.

O coletor roda na **máquina do Sergio**, a mesma do Projeto Conversão. Duas
consequências a assumir: a extração só acontece com aquela máquina ligada e na
rede da Egrey, e o upload pela tela continua sendo o caminho de emergência.

## A regra que atravessa tudo: código interno x código do ERP

No MN **toda tabela tem dois códigos**: um interno, inteiro, e o que aparece nas
telas, texto. Não é só datatype diferente — **o conteúdo é outro**. Cruzar um com
o outro não dá erro: dá número errado.

| Conceito | Interno (Int32) | Do ERP (String) |
|---|---|---|
| Produto | `PRODUTO` | `COD_PRODUTO` — `140000` |
| Cor | `COR` | `COD_COR` — `0002` |
| Estampa | `ESTAMPA` | `COD_EST` |
| Filial | `FILIAL` | `COD_FILIAL` — `00044` |
| Funcionário | `FUNCIONARIO` | `COD_FUNCIONARIO` — `000024` |

**A planilha só tem os códigos do ERP.** Todo cruzamento nosso é por eles.

Três armadilhas concretas nos métodos que vamos usar:

1. **`Detalhado2_Data` devolve `COR` e `COD_COR`.** `COR` é o interno; a cor que
   casa com a planilha é `COD_COR`. Pegar o campo errado faz o cruzamento com a
   aba Preco falhar em silêncio.
2. **`DadosPrecos` recebe `PRODUTO:Int32`** — quer o interno, que a planilha não
   tem. E `Detalhado2_Data` não devolve o interno do produto, só `COD_PRODUTO`.
   Vai precisar de um de-para.
3. **`Produto_Filial_Analitico` devolve os dois** (`PRODUTO` e `COD_PRODUTO`) —
   serve como o de-para do item anterior.

Nos parâmetros o padrão se repete: `PRODUTOI`/`PRODUTOF` são String (código do
ERP), enquanto `PRODUTO`, `COR` e `FILIAL` sozinhos são Int32 (interno). Ler o
tipo no `$metadata` antes de montar a chamada.

## De-para das filiais — `filiais/Lista_Filiais_SemFiltro`

Sem parâmetro nenhum, devolve `COD_FILIAL`, `FILIAL` e `NOME`. É a forma direta
de confirmar o que é cada código.

```
GET /api/millenium/filiais/Lista_Filiais_SemFiltro?$format=json
```

O de-para foi lido em 18/09/2026 — 39 filiais. As que interessam:

| cod_filial | interno | nome |
|---|---|---|
| `IGUATEMI` | 5 | EGREY CONFECÇÕES E COMERCIO DE ROUPAS - EIRELI - EPP |
| `EGREY JDS` | 104 | E. GREY CONFECÇÕES E COMÉRCIO DE ROUPAS |
| `00044` | 105 | E. GREY CONFECCOES E COMERCIO DE ROUPAS LTDA |
| `00065` | 49 | **SHOP ONLINE EGREY** |
| `00067` | 51 | FARFETCH FOTO |
| `ELENA SP` / `ELENA ES` | 101 / 102 | ELENATIMES ATACADO DO BRASIL LTDA — atacado |
| `SHOWROOM` | −2000000000 | não é loja |

### O Site: 00044 ou 00065?

**O nome não decide.** `00044` traz a razão social da empresa, que não diz nada
sobre canal; `00065` se chama literalmente SHOP ONLINE EGREY.

A favor do `00044`: é a filial que aparece com venda na amostra de 200
documentos do levantamento anterior, e o `00065` não apareceu — o que sugere que
`00065` está inativo ou é usado para outra coisa. Contra: o nome.

**Decide no número.** `coletor/valida_site.py` puxa a venda por filial do período
e compara com o que a planilha traz. No export de 18/09:

| | |
|---|---|
| Linhas | 45 |
| Peças líquidas | 21 (34 de saída, 13 de devolução) |
| Valor | R$ 25.548,44 |
| Produtos distintos | 35 |

| | JARDINS | IGUATEMI | SITE |
|---|---|---|---|
| Linhas | 317 | 293 | 45 |
| Peças líquidas | 112 | 152 | 21 |
| Valor | R$ 136.585,80 | R$ 183.579,10 | R$ 25.548,44 |
| Produtos distintos | 118 | 101 | 35 |

A filial cujo líquido e valor baterem com a coluna SITE é o e-commerce. Se
nenhuma bater, o período do export não é o que foi consultado.

```
python -m coletor.valida_site --de 2026-09-11 --ate 2026-09-17
```

Lembrando que pela API a devolução vem **positiva** com `tipo_operacao = "E"`,
enquanto a planilha já traz negativa — daí as 13 linhas negativas do SITE.

## Armadilhas que nos atingem

As três primeiras produzem número errado sem gerar erro, que é o pior caso.

1. **`$filter` e `$orderby` são ignorados em silêncio** — devolve 200 com dados
   fora do filtro. Período é só `DATAI`/`DATAF`.
2. **`TIPO=S` esconde a devolução** (evento 12 volta vazio). Filtrar só por evento.
3. **Devolução vem com valor e quantidade positivos**, marcada em
   `tipo_operacao = "E"`. Somar sem olhar esse campo infla o número.
4. **Itens com `quant = 0` são linha de pedido, não venda.** Destruiriam qualquer
   média por peça — e, no nosso caso, a contagem de vendas.
5. **Chamada sem `DATAI`/`DATAF` e sem `$top` trava** o servidor.
6. **`$top` trunca sem avisar.** Se vier exatamente `$top` itens, assuma corte.
   Uma chamada por dia resolve e ainda torna a extração idempotente.
7. **`EVENTO` aceita um valor por chamada.** Eventos de venda: 10, 30, 204.
   Devolução: 12.

## Datas

`data_emissao` vem no formato Microsoft `/Date(1757...000-180)/`. O offset **já
foi aplicado** pelo Millennium; reaplicar joga lançamento para o dia anterior.

```python
RE_DATA_MS = re.compile(r"/Date\((-?\d+)")

def parse_data_millennium(valor):
    if not valor:
        return None
    m = RE_DATA_MS.search(valor)
    return datetime.utcfromtimestamp(int(m.group(1)) / 1000).date() if m else None
```

Teste de sanidade: em varejo de moda sábado é o maior dia. Se o pico sair na
sexta, o fuso está sendo aplicado duas vezes.

## Os métodos das quatro fontes que faltavam

Encontrados no `$metadata` em 18/09/2026, procurando **pelos campos** que
precisamos, não pelo nome do método — nome de método não diz nada num schema com
5.413 deles. Nenhum foi chamado ainda: os campos e parâmetros abaixo vêm do
schema, o comportamento real ainda precisa ser conferido.

**O caminho sai do nome do tipo retornado.** `MILLENIUM_ESTOQUE_DETALHADO2_DATA`
→ `/api/millenium/estoque/Detalhado2_Data`. Regra confirmada contra os três
métodos já em uso (`MILLENIUM_MOVIMENTACAO_VENDAS_CONSULTA_COMPLETA` →
`/movimentacao/vendas_consulta_completa`).

### Estoque + cadastro — `estoque/Detalhado2_Data`

O achado mais útil: **cobre a aba Estoque e a aba Produtos numa chamada só.**

```
campos: COD_PRODUTO, DESCRICAO, ESTOQUE, ENTRADA, VENDA, TAMANHO,
        COR, COD_COR, DESC_COR, GRADE, MASTER,
        COD_DIVISAO, DESC_DIVISAO, COD_MARCA, DESC_MARCA,
        COD_TIPO, DESC_TIPO, COD_DEPARTAMENTO, DESC_DEPARTAMENTO,
        COD_COLECAO, DESC_COLECAO, COD_GRUPO, DESC_GRUPO,
        COD_PROD_FOR, COD_FORNECEDOR, NOME_FORNECEDOR, AGRUPA, DESC_AGRUPA
```

Traz o grão que o controle por cor precisa (produto + cor + tamanho) **e** todos
os atributos de filtro que a tela vai usar: coleção, divisão, departamento, tipo,
marca, grupo.

```
params: DATAI, DATAF                          período
        PRODUTOI, PRODUTOF, PRODUTO           faixa de produto
        COLECAO + SCRIPT_COLECOES             filtro por coleção (booleano + lista)
        DIVISAO + SCRIPT_DIVISOES
        DEPTO + SCRIPT_DEPTOS
        TIPO + SCRIPT_TIPOS
        MARCA + SCRIPT_MARCAS
        ANALISE, QUEBRA, AGRUPAMENTO, ORDEM   controlam o agrupamento — testar
        QTDE, TIPO_PROD
```

O padrão booleano + `SCRIPT_*` se repete: o booleano liga o filtro, a string traz
a lista. `Detalhado2` é a variante com `TAMANHOS` (plural, grade inteira em um
campo) em vez de `TAMANHO` — a `_Data` é a que serve para nós.

**Não traz filial.** Se o estoque por filial voltar a importar, é o método
abaixo.

### Estoque por filial — `estoque/Produto_Filial_Analitico`

```
campos: PRODUTO, COD_PRODUTO, DESC_PROD, COR, DESC_COR, ESTAMPA, DESC_EST,
        FILIAL, DADOSFILIAL, ESTOQUE, TOTEST, TOTAL_EST, SP_QUANT,
        TAMANHOS, SaldoQtde, TAMANHOSALDO, PRECOP, VALOR, TOTVLR, EVENTO
```

Mesma família de filtros, mais `SCRIPTFILIAL`/`FILIAIS`. Tem um parâmetro
`SALDOINICIAL:Boolean` que **vale investigar** — se devolver saldo de abertura
por produto e cor, resolve sozinho o ponto em aberto do roteiro.

### Preço — `produtos/DadosPrecos`

```
campos: PRODUTO, TABELA, COR, ESTAMPA, TAMANHO, PRECO, CUSTO, PRECO_COM_IPI
params: PRODUTOS:String (lista), TABELA, PRODUTO, DATA_PRECO, FILIAL,
        FORNECEDOR, UFBASE, TIPO_EMPRESA, LOTE, IPI_CONSIDERAR
```

É exatamente o grão da aba Preco (Produto + Código Cor + Tamanho → Preço), com
`DATA_PRECO` de brinde — preço histórico, que a planilha não tem.

Alternativa: `precos/LocalizaMultiplos`, que traz `COD_PRODUTO` e
`DESCRICAO_TABELA` junto, mas recebe a lista de produtos como estrutura em vez
de string.

**Atenção à tabela de preço.** Os dois métodos têm `TABELA` como parâmetro; a
planilha não diz qual tabela usa. Descobrir antes de confiar no Nível de Estoque.

### Produção — `producao/Entradas_Via_Producao`

```
campos: N_ORDEM, DATA, DESC_PRODUTO, QTDE, QTDES, TAMANHOS,
        COR, ESTAMPA, FILIAL, DEFTO, DEFTOS, QTDEFEITO
params: DATAI, DATAF, PRODUTOI, PRODUTOF, SCRIPTFILIAL/SELFILIAL,
        AGRUPAR, AGRDATAS, AGRFILIAIS,
        SCOLECAO/BCOLECAO, SGRUPO/BGRUPO, SMARCA/BMARCA,
        SCATEGORIA/BCATEGORIA, SDEPARTAMENTO/BDEPARTAMENTO,
        STIPO/BTIPO, SDIVISAO/BDIVISAO, SSUBCOLECAO/BSUBCOLECAO
```

Entradas por produção **no período**, com data e número de ordem — melhor que a
planilha, que só traz o acumulado sem data. É o que a tabela `movimento` do novo
modelo precisa para registrar entrada com data.

`DEFTO` e `QTDEFEITO` sugerem que defeito vem separado da quantidade boa;
confirmar se `QTDE` já é líquida.

Para acompanhar ordem em andamento: `producao/Consulta_Ordem_Producao`, com
situação, fase, oficina, perdas e defeitos.

### O que testar na primeira chamada

1. `Detalhado2_Data` de um dia, e comparar o estoque total com a planilha da
   semana — hoje são 9.844 peças em 845 combinações de código e cor
2. Descobrir qual `TABELA` de preço a planilha usa, conferindo o Nível de Estoque
3. `Produto_Filial_Analitico` com `SALDOINICIAL=true`, para ver o que volta
4. `Entradas_Via_Producao` num período conhecido, conferindo contra a aba
   Producao da planilha
5. Qual código de filial é o Site

## O que ainda falta descobrir

O documento de origem cobre **venda** em profundidade. Para o sellout faltam
quatro fontes, todas descobríveis pelo `$metadata`:

| Fonte | Situação |
|---|---|
| Vendas | Em uso — `movimentacao/vendas_consulta_completa` |
| Estoque atual | Candidato — `estoque/Detalhado2_Data` |
| Preço | Candidato — `produtos/DadosPrecos` |
| Produtos (cadastro) | Sai junto com o estoque no `Detalhado2_Data` |
| Produção | Candidato — `producao/Entradas_Via_Producao` |

Os candidatos vieram do `$metadata` e **ainda não foram chamados**. Detalhe de
cada um na seção anterior.

Procedimento, da seção 8 do documento original:

```
GET /api/millenium/$metadata      (7,9 MB · 5.413 métodos · 5.634 tipos)
```

Baixar uma vez, procurar o `FunctionImport` pelo nome do método (dá os
parâmetros exatos) e o `EntityType` do `ReturnType` (dá os campos da resposta).
**Só então** chamar. Sondar às cegas custa muito mais.

## Pontos em aberto específicos do sellout

**A filial SITE.** A planilha de vendas separa Jardins, Iguatemi e Site. Na
amostra da API apareceram `EGREY JDS`, `IGUATEMI`, `00044`, `ELENA ES` e
`ELENA SP` — nenhuma obviamente é o e-commerce. Sem saber qual código é o Site,
a coluna Vendas Site não pode ser reproduzida.

Filial exige lista branca no nosso código: `ELENA ES` e `ELENA SP` são atacado,
outra operação, e numa amostra de 200 documentos responderam por quase toda a
receita. Puxar tudo misturado torna o número irreconhecível.

**Troca e retirada de compra online não têm evento próprio** — saem misturadas
nos eventos de venda. Importa aqui porque a retirada de uma compra do site numa
loja pode aparecer como venda da loja, deslocando o rateio entre Jardins,
Iguatemi e Site.

**Quantidade líquida.** O export atual de Vendas já traz quantidade negativa para
devolução, ou seja, vem líquido. Pela API vem positivo com `tipo_operacao = "E"`.
Para dar o mesmo número: `quantidade = saídas − entradas`, ignorando linhas com
`quant = 0`.

**Cor e tamanho.** `itens[]` traz `cod_produto`, `cor`, `tamanho` e `estampa` —
o grão que o controle por cor precisa. Confirmar se `cor` vem como código (0002)
ou nome (PRETO); o cadastro de cores é global, 68 códigos sem ambiguidade.

**Ao casar itens, ler as chaves por presença, não por verdade.** `estampa` pode
valer `0`, e `item.get("estampa") or item.get("ESTAMPA")` faz o mesmo produto
deixar de casar consigo mesmo.

## Antes de confiar em qualquer número

- Rodar em modo que só imprime, sem gravar
- Comparar um dia contra o relatório do próprio ERP
- Conferir se o relatório de comparação é bruto ou líquido — comparar bruto
  contra líquido acusa ~9% de diferença que não existe
- Olhar a distribuição por dia da semana (fuso)
- Conferir o estoque total contra a planilha da semana antes de substituir a
  fonte
