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

## O que ainda falta descobrir

O documento de origem cobre **venda** em profundidade. Para o sellout faltam
quatro fontes, todas descobríveis pelo `$metadata`:

| Fonte | Situação |
|---|---|
| Vendas | Resolvido — `movimentacao/vendas_consulta_completa` |
| **Estoque atual** | Método desconhecido |
| **Preço** | Método desconhecido |
| **Produtos** (cadastro, coleção, divisão, departamento) | Método desconhecido |
| **Produção** | Método desconhecido |

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
