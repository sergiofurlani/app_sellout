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

### Como rodar os scripts do coletor

Na **sua máquina**, dentro da rede da Egrey — não no Railway, não em nuvem. O
Railway nunca alcança o MN, e é por isso que o coletor existe como programa
separado (ver a seção seguinte).

Abra o PowerShell na pasta do repositório — a mesma onde ficam `sellout/` e
`coletor/` — e defina as três variáveis. A senha tem `#`, então vai entre aspas
**simples**; com aspas duplas o PowerShell corta no `#` e o resultado é um 401
que parece senha errada:

```powershell
cd C:\caminho\para\app_sellout

$env:EGREY_API_URL     = 'http://egray.millenniumhosting.com.br:6017'
$env:EGREY_API_USUARIO = 'int-egray'
$env:EGREY_API_SENHA   = 'a-senha-com#'

python -m coletor.valida_site --de 2026-09-11 --ate 2026-09-17
python -m coletor.explora_entradas --de 2026-09-01 --ate 2026-09-17
```

As variáveis valem só naquela janela do PowerShell. Fechou, sumiram — o que é
bom: a senha não fica em lugar nenhum.

Nada precisa estar instalado além do Python: o `coletor` usa só biblioteca
padrão, de propósito, para rodar em qualquer máquina da rede sem `pip install`.

`python -m coletor.x` (com ponto, sem `.py`) só funciona a partir da raiz do
repositório. Rodar de dentro da pasta `coletor` dá `No module named coletor`.

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

**A lista branca muda conforme a fonte.** O e-commerce não tem estoque próprio —
vende do estoque das lojas — então entra em vendas e fica **fora** de estoque,
senão o saldo das lojas é contado duas vezes (ver D12 em `decisoes.md`).

Atenção também ao rótulo: no export de estoque as lojas aparecem como
`EGREY JARDINS` e `EGREY IGUATEMI`, enquanto o de-para de filiais traz
`EGREY JDS` e `IGUATEMI`. Casar por `cod_filial` ou pelo interno, nunca pelo
nome.

### O Site é o `00044` — confirmado em 19/09

O nome nunca ia decidir: `00044` traz a razão social da empresa, que não diz
nada sobre canal, e `00065` se chama literalmente SHOP ONLINE EGREY.

Decidiu o número. Varredura de 35 dias (15/08 a 18/09), com os eventos de
e-commerce já incluídos:

- **`00044` aparece com venda**: 333 linhas, 181 peças líquidas, R$ 209.801,29.
- **`00065` não aparece em nenhum dia.** Cadastro morto, como o negócio dizia.

A melhor janela de 7 dias, contra a coluna SITE do export:

| | API (31/08 a 04/09) | Planilha |
|---|---|---|
| Peças líquidas | 20 | 21 |
| Valor | R$ 24.797,97 | R$ 25.548,44 |
| Produtos distintos | **35** | **35** |

Produtos distintos bate exato; a diferença é **uma peça de R$ 750,47** — um item
só, de um produto que já estava no conjunto. Não é erro de regra nem de filial.

**Período do export: 31/08 a 07/09.** Puxado em 08/09, cobrindo até o dia 07 —
feriado em São Paulo, lojas abertas. A rodada manual anterior tinha sido em
31/08. O arquivo só chegou ao projeto em 18/09, e tratar a data de chegada como
data do conteúdo custou duas varreduras.

### O resultado da validação (19/09)

| | API | Planilha | diferença |
|---|---|---|---|
| **IGUATEMI** | 152 peças · R$ 183.579,10 | 152 · R$ 183.579,10 | **zero, ao centavo** |
| JARDINS | 110 peças · R$ 136.362,80 | 112 · R$ 136.585,80 | 2 peças · R$ 223,00 |
| SITE | 20 peças · R$ 24.797,97 | 21 · R$ 25.548,44 | 1 peça · R$ 750,47 |

IGUATEMI bater **ao centavo** é o que valida a regra de agregação inteira:
linha de quantidade zero ignorada, devolução chegando positiva e subtraída,
`valor_acerto` somado uma vez por documento. Nenhuma dessas convenções erra e
ainda assim acerta 152 peças e R$ 183.579,10 por acidente.

Sobram **3 peças e R$ 973,47 em 285 peças e R$ 345.713** — 1,05% e 0,28%,
concentrados em duas filiais. Com a regra provada certa pela terceira, o resíduo
é de documento, não de método. A hipótese mais provável é **cancelamento
posterior ao export**: a planilha congelou o ERP em 08/09, a API mostra o ERP de
hoje. Uma venda cancelada depois desaparece de um lado e não do outro.

Isso não é defeito a corrigir — é argumento a favor do retrato semanal imutável
no banco (D9).

**O Site não mudou nada entre 04/09 e 07/09**: mesmas 20 peças, mesmo valor,
mesmas 35 linhas. Três dias — sábado, domingo e feriado — com zero faturamento
de e-commerce. Confirma que o evento `00003` marca a emissão da nota, em dia
útil, e não o pedido.

**Produtos distintos não é comparável**, pelo mesmo motivo que linhas: a aba
Vendas conta linha de quantidade zero, que é pedido e não venda. JARDINS mostra
75 pela API contra 118 na aba, com 134 linhas contra 317.

### O erro de método que precedeu isso

A primeira varredura pontuava **só o SITE** e apontou 31/08–04/09, onde o Site
batia 96% e as duas lojas ficavam em 64% e 66% — as duas com a mesma razão, o
que já denunciava fatia faltando, não ruído.

31/08–04/09 é segunda a sexta. O Site batia ali **porque** o fim de semana
estava de fora. Otimizar contra uma coluna só encontra o recorte que mais
favorece aquela coluna — que era, por construção, o que mais escondia o buraco
das outras duas. A varredura agora soma o erro das três e testa vários tamanhos
de janela.

Referência completa do export, para comparações futuras:

| | JARDINS | IGUATEMI | SITE |
|---|---|---|---|
| Linhas | 317 | 293 | 45 |
| Peças líquidas | 112 | 152 | 21 |
| Valor | R$ 136.585,80 | R$ 183.579,10 | R$ 25.548,44 |
| Produtos distintos | 118 | 101 | 35 |

Linhas não são comparáveis: a planilha conta linha de quantidade zero (pedido),
o coletor não. Comparar peças, valor e produtos.

```
python -m coletor.valida_site --de 2026-08-31 --ate 2026-09-04
python -m coletor.valida_site --de 2026-08-15 --ate 2026-09-18 --varrer
```

### ELENA ES só devolve

Nos 35 dias: 0 peças de saída, 32 de devolução, R$ -30.026,00. A venda de
atacado sai por eventos que não estão nesta lista, mas a **devolução volta pelo
evento de varejo** — então ela entra na extração sem que nada de venda entre.

Isso confirma a D12 pelo motivo contrário ao esperado: ELENA ES tem que ser
excluída **pelo nome**, porque ignorá-la não a mantém de fora — mantém só um
saldo negativo solto.

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

## Entrada de estoque nas lojas — `transferencias/Transferencia_Filiais`

A peça que faltava para o Estoque inicial (D13). A produção chega inteira na
Elena; o que vira estoque de loja é a movimentação da ELENA ES para Jardins e
Iguatemi, registrada por um evento de **"venda entre filiais"**.

```
campos: DATA, ROMANEIO, NOTA, TAMANHO, GRADE,
        PRODUTO (Int32, interno), COD_PRODUTO (String, do ERP),
        COR (Int32, interno), DESC_COR (nome), ESTAMPA, DESC_ESTAMPA,
        DESC_FILIALO, DESC_FILIALD,        origem e destino, por descrição
        QUANTS, TAMANHOS, PRECOS (String)  provavelmente a grade
        QUANTS_S, PRECOS_S, UNIT_M (Decimal)

params: DATAI, DATAF                       período
        SCRIPTFILIALO + BORIGEM            filial de origem — ELENA ES
        SCRIPTFILIALD + BDESTINO           filial de destino — as lojas
        SCRIPTEVENTO + BEVENTO             restringe ao evento certo
        SCRIPTCOR + BBCOR, PRODUTOI/PRODUTOF, ROMANEIO, NOTA
        QUEBRA, ORDEM, IMPRESSAO, LAYOUT   controlam o agrupamento — testar
```

**Não devolve `COD_COR`.** Traz `COR` (interno) e `DESC_COR` (nome), e a planilha
cruza por código (`0002`). Casar por nome é frágil, então o caminho é montar o
de-para `COR → COD_COR` a partir do `Detalhado2_Data`, que devolve os dois.

`QUANTS` e `TAMANHOS` são String enquanto `QUANTS_S` é Decimal — provável que os
primeiros tragam a grade inteira e o segundo o total. Confirmar na primeira
chamada; muda como a quantidade é lida.

### `eventos/ListaEventosPorTipo` é o catálogo — o outro não é

Use **este** para saber quais eventos existem. Responde sem parâmetro e devolve
entrada **e** saída, com `EVENTO`, `CODIGO`, `DESCRICAO`, `TIPO_ENTRADA`,
`TIPO_SAIDA` e `GRUPO_EVENTO`. Foi ele que preencheu `09`, `00027` e `00206`
para os eventos de venda, que o outro método não tem.

`Eventos_InfluenciaEstoque` promete pelo nome o que não entrega: "influência de
estoque" sugere tudo que mexe no saldo, e venda mexe. Mas ele devolve 20 linhas,
**todas de entrada**. Tratar o nome como contrato levou a concluir que o evento
de venda entre filiais "não existe", quando o que não existia era na lista.

Serve para uma coisa: é a lista curta dos eventos de entrada, útil para
restringir candidatos. Não serve como catálogo.

### Os eventos de entrada — `eventos/Eventos_InfluenciaEstoque`

Sem parâmetro nenhum. Devolve `EVENTO` (interno), `CODIGO` (do ERP) e
`DESCRICAO`.

```
GET /api/millenium/eventos/Eventos_InfluenciaEstoque?$format=json
```

**Chamado em 18/09: devolveu 20 eventos, todos de entrada.** O evento de saída
"venda entre filiais" não aparece aqui — este método lista só o lado que
*entra* no estoque. E é justamente esse o lado que interessa: o Estoque inicial
é a entrada na loja, não a saída da Elena.

Os candidatos, em ordem de probabilidade:

| evento | código | descrição | leitura |
|---:|---|---|---|
| 105 | `00107` | RECEBIMENTO DE COMPRA P.A (LOJAS) | **mais provável** — produto acabado, destino explícito lojas |
| 104 | `00106` | RECEBIMENTO DE COMPRA ELENATIMES ES | origem explícita, destino não |
| 13 | `12` | RECEBIMENTO DE TRANSFERENCIA MATRIZ | se a Elena for tratada como matriz |
| 103 | `00105` | RECEBIMENTO DE COMPRA P.A | genérico |
| 115 | `00123` | RECEBIMENTO ELENATIMES (ATACADO) | **fica de fora** — é o atacado |

O par `00107` (LOJAS) x `00123` (ATACADO) é o mesmo corte varejo/atacado que o
negócio descreve. Isso é indício forte, não prova: só a chamada decide.

### O e-commerce tem eventos próprios — e isso escondia o Site

Primeira rodada do `valida_site`, 19/09: voltaram **só IGUATEMI, EGREY JDS e
ELENA ES**. Nenhuma linha de Site — nem `00044`, nem `00065`.

A causa: o coletor perguntava por 10, 30, 204 e 12, que vieram do estudo de
**venda de loja**. O e-commerce fatura por evento separado:

| código | descrição | sinal |
|---|---|---|
| `00003` | FATURAMENTO E-COMMERCE | venda |
| `00002` | DEVOLUÇÃO DE VENDA E-COMMERCE | devolução |
| `00004` | DEVOLUÇÃO TROCA/CUPOM E-COMMERCE | devolução |

Lição geral: **filtrar por evento é filtrar por canal sem perceber.** Uma lista
de eventos incompleta não dá erro nem vem vazia — vem plausível, faltando um
canal inteiro. Foi assim que o Site sumiu sem ninguém notar.

O catálogo completo, com entrada e saída, sai de
`eventos/ListaEventosPorTipo` (`Eventos_InfluenciaEstoque` só traz entrada).

### A armadilha do código do evento

O par interno x ERP morde aqui de um jeito especialmente feio:

```
evento 12  = DEVOLUÇÃO DE VENDA VAREJO        código "11"
evento 13  = RECEBIMENTO DE TRANSFERENCIA     código "12"
```

O `12` existe dos dois lados, **apontando para eventos diferentes**. O coletor
já usa `EVENTO=12` para devolução e funciona — o que confirma que o parâmetro
`EVENTO` recebe o **inteiro interno**, nunca a string `CODIGO`. Trocar os dois
não dá erro: devolve transferência no lugar de devolução, em silêncio.

Para ver quais filiais usam um evento: `filiais/Lista_FilialXEventos`.

**Aviso que vale para a agregação de venda:** o evento de venda entre filiais
não pode entrar no sellout como venda. Como a extração filtra por evento
(10, 30, 204 para venda e 12 para devolução), ele já fica de fora — mas quem
mexer nessa lista precisa saber por quê.

### `saidas/MovimentacaoPorGrade` — resolve o buraco do `COD_COR`

Achado ao procurar o evento. É o método mais bem formado que vimos para o
sellout: devolve **os dois códigos do ERP**, com grade e evento.

```
campos: COD_PRODUTO (String), REFERENCIA, DESC_PRODUTO, DESC_MARCA,
        COD_COR (String), DESC_COR,        <- o que faltava
        COD_FILIAL (String), DESC_FILIAL,
        DATA, DESC_EVENTO, GERADOR,
        QUANTIDADES, TAMANHOS (String), QTDE (Decimal), GRADE

params: DATAI, DATAF, TIPO, QUEBRA, BPRODUTO, PRODUTOINI, PRODUTOFIM,
        SCRIPTFILIAL/FILIAL, SCRIPTEVENTO, SCRIPTCOLECAO, SCRIPTTIPO, ...
```

Dois usos:

1. **De-para `COR → COD_COR`** — dispensa montar pelo `Detalhado2_Data`.
2. **Talvez a extração inteira** — tem período, filial, evento, produto, cor e
   grade. Traz **uma** filial por linha (`COD_FILIAL`), então para transferência
   ainda é preciso saber se essa filial é origem ou destino; é o que o
   `Transferencia_Filiais` dá de graça com `DESC_FILIALO`/`DESC_FILIALD`.

**Os dois são relatórios e recusaram a chamada simples** (19/09):

```
Transferencia_Filiais : value of parameter LAYOUT, not found in list
MovimentacaoPorGrade  : value of parameter QUEBRA, not found in list
```

Erro bom: o caminho da URL está certo — o servidor chegou a executar a macro e
parou na validação do parâmetro. `LAYOUT` e `QUEBRA` são obrigatórios e só
aceitam valores de uma lista que o `$metadata` **não publica**, e nenhum método
do tipo `ListaLayouts` existe. Descobrir esses valores é tentativa e erro.

Por isso a sondagem passou a usar `movimentacao/vendas_consulta_completa`, que
já está provado e devolve os itens com produto e cor, e
`movimentacao/Lista_Por_Evento`, que traz `FILIAL_DESTINO` no documento. Os
relatórios ficam para quando fizerem falta.

**Regra geral que sai daí:** método de relatório (`LAYOUT`, `QUEBRA`, `ORDEM`,
`IMPRESSAO`) é feito para a tela do ERP e cobra parâmetros de apresentação.
Método de consulta (`DATAI`, `DATAF`, `EVENTO`, `FILIAL`) é feito para ser
chamado. Preferir o segundo sempre que existir.

## O `$metadata` responde mais do que eu supunha (21/09)

Três coisas que eu vinha adivinhando e estão escritas no arquivo:

**1. O grupo do caminho é o `EntitySet`, não o container.** O arquivo inteiro
tem **um** `EntityContainer`, chamado `millenium`, e 461 `EntitySet` dentro
dele. `/api/millenium/produtosac/Lista` é `EntitySet="PRODUTOSAC"` +
`FunctionImport Name="Lista"`. Procurar pelo container faz todo método virar
`millenium/X`, que não existe como URL.

**2. Os nomes e tipos dos parâmetros estão publicados.** Só os *valores* de
lista fechada é que não. O `produtosac/Lista` declara `CAMPO` e `ORDEM` como
`Int32` — por isso `CAMPO=0, ORDEM=0` funcionou e as quinze tentativas com
texto falharam. O `QUEBRA` do `MovimentacaoPorGrade` é `Boolean`, o que
explica de graça o *"Could not convert variant of type (String) into type
(Boolean)"* que me custou duas rodadas.

**3. O `ReturnType` diz os campos sem chamar o método.** Ele aponta para um
tipo declarado no mesmo arquivo. Foi assim que se descobriu o que o
`precos/Lista` devolve, mesmo ele respondendo vazio.

`coletor/sonda_parametros.py --procurar` e `--parametros` fazem as três
leituras. A sonda por tentativa continua existindo só para o que sobra: os
valores das listas fechadas.

### As duas fontes que faltavam, achadas aqui

| método | parâmetros | devolve |
|---|---|---|
| `estoque/Lista` | `ORDEM`, `SCRIPTFILIAL`, `LOJA`, `COR`, `ESTAMPA`, `TAMANHO`, `TIPO`, `LOTE` | `COD_PRODUTO`, `COR`/`DESC_COR`, `TAMANHO`, `QUANTIDADE`, `EMPENHADO`, `TOTAL`, `FILIAL`/`DESC_FILIAL` |
| `precos/ConsultaParaExportarPlanilha` | `PRODUTOS` (coleção), `EXPORTA_BARRA` | `COD_PRODUTO`, `COD_COR`, `TAMANHO`, `BARRA_EAN`, `PRECO` |
| `precos/Lista` | `TABELA`, `PRODUTO`, `COR`, `TAMANHO`, validade… | `TABELA`/`DESC_TABELA`, `PRECO`, `COR`, `TAMANHO`, validade — **um produto por chamada** |

`estoque/Lista` é a aba Estoque inteira: produto, cor, tamanho, filial e
quantidade, com `EMPENHADO` de brinde. `precos/Lista` cobra `PRODUTO` e serve
para conferir um item; para a aba Preço inteira o candidato é o
`ConsultaParaExportarPlanilha`, cujo `PRODUTOS` é uma coleção — falta
descobrir como passá-la numa chamada GET.

**Existe um segundo namespace, `MILLENIUM_ECO`**, que este `$metadata` não
cobre — é a API do e-commerce, com métodos próprios como
`PRODUTOS.PRECODETABELA`, que aceita `PRODUTOS=` e `TABELA1..4`. Se ele
devolver a tabela inteira numa chamada, resolve o preço melhor que os dois
acima. Ainda não foi testado.

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
