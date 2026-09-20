# Decisões

Registro das decisões tomadas, em ordem cronológica. Cada uma diz **o que** foi
decidido, **por quê**, e o que muda se for revista. Serve para não refazer
discussão já fechada — e para saber onde mexer quando a regra mudar.

---

## D1 · O texto em vermelho divide o código entre as linhas

Quando o mesmo código ocupa duas linhas nas abas Masculino/Feminino, o trecho
escrito em vermelho ao final da descrição diz de quais cores aquela linha trata.
A linha sem vermelho fica com as cores restantes; `DEMAIS CORES` significa a
mesma coisa.

A comparação ignora acentos e resolve abreviações (`OFF` → `OFF-WHITE`,
`VERDE CL` → `VERDE CL.`, `AMARELA` → `AMARELO`).

**Por quê:** a planilha é organizada por produto, mas o negócio precisa separar
algumas cores. O vermelho era a convenção que já existia.

**Se for revista:** no modelo por cor (ver D9) essa regra deixa de ser
necessária. É a maior simplificação que a migração traz.

## D2 · Códigos sem divisão identificável ficam intocados

`212006` (vermelho diz "CORES SS25", que não é cor) e `330011` (duas linhas
idênticas, nenhuma em vermelho) não são alterados. Ficam marcados `MANTER` na
coluna A.

**Por quê:** melhor não mexer do que distribuir errado em silêncio.

## D3 · Cor sem saldo na semana não trava a divisão

Se o vermelho cita uma cor que zerou o estoque, ela contribui zero e a linha
segue valendo. Só texto que não é cor em nenhuma aba de origem trava.

**Por quê:** a primeira versão travava o código inteiro quando uma cor esgotava,
o que acontece toda semana.

## D4 · Estoque atual soma todas as filiais do arquivo

As filiais presentes no export entram na soma. Quando a coluna Filial vem em
branco, tudo entra.

**Histórico:** eram 3 filiais (E. GREY, EGREY JARDINS, EGREY IGUATEMI); a
E. GREY saiu do export em 31/08 e o estoque caiu de 12.737 para 9.450 peças. Na
época ficou como risco em aberto — **era intencional, e está certo**: ver D12.

A tela de revisão lista as filiais que encontrou, para uma queda dessas nunca
passar despercebida.

## D5 · Produção só entra se houver estoque

A quantidade da aba Produção só é somada ao Estoque inicial se o produto tiver
estoque atual maior que zero. Mesma regra para incluir produto novo.

**Por quê:** decisão do usuário em 31/08. Produção de item sem estoque fica
listada no relatório, aguardando o estoque aparecer.

## D6 · Produto novo entra ao final do bloco da sua coleção

A coleção vem da coluna COL da aba Produtos e é casada com o nome do bloco na
coluna C das abas de trabalho. As fórmulas da linha são replicadas do bloco.

Para produto novo, Estoque inicial = `max(produção, estoque atual + vendas)`.

**Por quê:** sem esse `max`, um item com estoque e sem produção registrada gera
Consignado negativo.

## D7 · Nível de Estoque cruza Estoque com Preço

Valor = Σ (quantidade × preço), com o preço vindo da aba Preco por
**Código + Código Cor + Tamanho**. Sem preço exato, cai para o preço do mesmo
código e a linha é reportada.

As linhas de peças e preço médio viraram fórmulas vivas, em vez de texto fixo.

## D8 · As colunas das abas de origem são localizadas pelo cabeçalho

Não por posição. Além disso o conteúdo é validado: se a coluna do número não for
numérica, o app procura a próxima que seja; tamanho e código da cor são
conferidos contra o vocabulário da aba Preco.

**Por quê:** em 08/09 inseriram uma coluna Estampa na aba Estoque sem ajustar a
linha 1. O rótulo "ESTOQUE ATUAL" ficou sobre os tamanhos e o app somou
38+40+42, multiplicando o estoque por ~15. Passou despercebido até a conferência
visual. A tela de revisão agora mostra de onde cada número vem, com amostra.

## D9 · Migrar para banco, com controle por cor

Decidido em 18/09. Motivos, em ordem de peso:

1. **Erro deixa de acumular.** Hoje a saída de uma semana é a entrada da
   seguinte: qualquer defeito se propaga e só aparece semanas depois — foi o que
   aconteceu quando o app apagou o texto em vermelho. Com banco, cada semana é
   um retrato imutável e o relatório é derivado.
2. **O nível de cor já existe na origem.** Estoque, Vendas e Preço trazem código
   de cor. São 845 combinações contra 458 produtos (~1,8 cores por produto).
3. **A regra D1 desaparece.** Todo o mecanismo do vermelho existe só para
   contornar uma grade por produto.
4. **O histórico para de crescer de lado.** Já são 237 colunas.

O Excel continua saindo como exportação enquanto a tela ganha confiança.

## D10 · Estoque inicial vira saldo com movimentos

O valor de hoje (as fórmulas `=86-1+44`) é congelado como saldo de abertura numa
data-base. Dali em diante as entradas passam a ser registradas como movimentos,
com data e origem.

**Por quê:** decisão do usuário. É o único dado do processo que não vem do ERP —
é conhecimento do negócio que mora na planilha.

**Revisto em 18/09 (ver D13): o Estoque inicial provavelmente não precisa ser
mantido na mão.** A entrada no estoque das lojas é a transferência da ELENA ES
para elas, e isso está no MN, com data, produto, cor e tamanho.

## D11 · A linha comercial é dado nosso

HOME, GLORIA KALIL, PIMA, CASHMERE, COURO e as coleções não existem como campo
no ERP — hoje são o nome do bloco na planilha. Viram atributo próprio do
produto, editável no app.

## D12 · O e-commerce não tem estoque próprio

O Site vende do estoque das lojas. Então a filial do e-commerce entra em
**vendas** e fica de fora de **estoque** — contá-la duplicaria o saldo das lojas.

Foi por isso que a filial E. GREY saiu do export de estoque em 31/08: orientação
dada à origem, não defeito. A queda de 12.737 para 9.450 peças foi a correção de
uma contagem dobrada.

**Consequência para o coletor:** a lista branca de filiais é **diferente por
fonte**.

| Fonte | Filiais |
|---|---|
| Estoque | só lojas físicas — `IGUATEMI` e `EGREY JDS` |
| Vendas | lojas físicas **e** o Site (`00044`) |
| Entrada de estoque | transferências de `ELENA ES` **para** as lojas (ver D13) |

`ELENA SP` e `ELENA ES` são produção e venda no atacado: **não entram no sellout
como venda**, só como origem das peças. `00065` (SHOP ONLINE EGREY) é cadastro
antigo, fora de uso. `SHOWROOM`, `BAZAR`, `LAVANDERIA`, `CONSERTOS` e os demais
também ficam de fora.

**Efeito colateral no sellout por cor:** como a venda do Site sai do estoque das
lojas, uma cor pode vender pelo Site e baixar do estoque de Jardins. O sellout
por cor continua correto no total, mas atribuir venda do Site a uma loja
específica não faz sentido — e a retirada de compra online na loja, que não tem
evento próprio no MN, embaralha ainda mais essa fronteira.

## D13 · O Estoque inicial é a transferência da ELENA ES para as lojas

A produção chega **inteira** na Elena — varejo e atacado juntos. O que vira
estoque de loja é a **transferência da ELENA ES para Jardins e Iguatemi**. É essa
movimentação, e não a produção total, que forma o Estoque inicial.

**Por que isso importa tanto:** o Estoque inicial era o único dado do processo
que não vinha do ERP — uma coluna mantida na mão, com fórmulas do tipo
`=86-1+44-2` acumulando ajustes de meses. Era também o denominador do sellout, o
que fazia dele o ponto mais frágil de toda a migração.

Se a transferência responde por ele, o Estoque inicial **deixa de ser digitado e
passa a ser derivado**, com data, produto, cor e tamanho — inclusive resolvendo o
saldo de abertura por cor, que estava em aberto na D10.

**Como a Egrey registra:** por um evento chamado **"venda entre filiais"**. Ou
seja, a movimentação não é um tipo próprio de documento — é uma venda com evento
específico, da ELENA ES para a loja.

Isso tem duas consequências opostas, e as duas importam:

- **Entrada de estoque:** é esse evento que forma o Estoque inicial das lojas.
- **Venda:** esse evento **não pode** entrar no sellout como venda, senão a
  receita de varejo infla com movimentação interna.

### Resolvido em 20/09 — é o evento 106

A peça entra na loja pela **venda entre filiais**, evento interno **106**
(`00108`), 1.186 movimentos em 2026. E a direção está em dois campos que não
parecem filial:

```
cod_filial   = quem emite   -> origem
cod_cliente  = para quem    -> destino
```

Na venda entre filiais **a loja é cliente da Elena**. Foi isso que escondeu o
destino durante toda a investigação: procurávamos `filial_destino`, que existe
nos métodos de relatório e vem vazio aqui.

Semana de 31/08 a 07/09:

| fluxo | docs | peças |
|---|---:|---:|
| ELENA ES → EGREY JDS | 18 | 305 |
| ELENA ES → IGUATEMI | 16 | 228 |
| EGREY JDS → ELENA ES | 1 | −2 |
| | | **531 líquido** |

**32 combinações produto+cor, 20 produtos.** O item traz `cod_produto`,
`cod_cor`, `desc_cor` e `tamanho` — os códigos do ERP, os mesmos da planilha.
Nada de de-para de cor: o saldo de abertura sai por cor direto, o que fecha
também o ponto em aberto da D10.

### A produção não é o que entra na loja — e a diferença é de 56%

Comparando, por código, a aba Producao (o que chegou na Elena) com a
transferência para as lojas na mesma semana:

```
producao total     826 peças   em 20 produtos
transferido        531 peças   em 20 produtos
diferença          295 peças
```

Os 295 são atacado e o que ficou na Elena. O padrão por produto confirma a
leitura em vez de contrariá-la:

- **`334059`: 56 peças produzidas, 0 transferidas.** Pela regra atual essas 56
  entram no Estoque inicial de uma loja que não recebeu peça nenhuma.
- **`334016`: 0 produzidas, 14 transferidas.** Produção de semana anterior,
  enviada agora. Produzir e despachar não acontecem no mesmo dia, e é
  justamente por isso que uma coluna não pode ser usada no lugar da outra.

Cinco produtos aparecem só na transferência e quatro só na produção — todos
casos de defasagem, nenhum de contradição.

**Conclusão:** somar a aba Producao ao Estoque inicial infla o denominador do
sellout. `coletor/estoque_inicial.py` extrai o número certo.

### Quanto isso custa, produto a produto

Simulação sobre o arquivo de 18/09, aplicando a D6 (`Estoque inicial =
max(produção, estoque + vendas)`) contra a mesma regra com a transferência no
lugar da produção. Só produtos com estoque, como manda a D5:

| código | estoque | vendas | produção | transferido | EI hoje | EI certo | erro |
|---|---:|---:|---:|---:|---:|---:|---:|
| 334127 | 2 | 1 | 31 | 10 | 31 | 10 | **+210%** |
| 334128 | 11 | 2 | 86 | 34 | 86 | 34 | **+153%** |
| 334066 | 40 | 0 | 111 | 48 | 111 | 48 | **+131%** |
| 334044 | 30 | 4 | 106 | 52 | 106 | 52 | **+104%** |
| 334037 | 15 | 0 | 50 | 29 | 50 | 29 | +72% |
| 239051 | 43 | 1 | 80 | 48 | 80 | 48 | +67% |
| 239028 | 40 | 6 | 65 | 56 | 65 | 56 | +16% |
| **total** | | | | | **1.124** | **864** | **+30%** |

Trinta por cento a mais no denominador. Como o sellout é vendas dividido por
Estoque inicial, o percentual sai cerca de **23% abaixo do real** no conjunto —
e, no `334127`, sai três vezes menor: 3% quando é 10%.

E são justamente os produtos da coleção nova, que é onde a decisão de repetir,
aumentar ou cortar é tomada. O erro está concentrado exatamente onde o número é
usado para decidir.

Um caso que a regra atual já protegia, e vale registrar: o `334059` teve 56
peças produzidas e nenhuma transferida, mas também nenhum estoque na loja — a
D5 o deixou de fora por isso. A regra "produção só entra se houver estoque" era
um remendo que, sem saber, corrigia parte deste mesmo problema.

### O que continua em aberto

Três eventos mexem no estoque da loja e **não aparecem** em
`vendas_consulta_completa` — são movimento direto, sem cliente e sem nota, e o
método só enxerga documento de venda.

**`ENTRADA SIMPLES DE ESTOQUE PRODUTO` (interno 0, 312/ano) e `SAÍDA SIMPLES PA`
(interno 2, 98/ano) são a correção de erro no envio para a loja** — mandou peça
errada, dá baixa e entrada para acertar. Explicado pelo negócio em 20/09.

Então eles **fazem parte do Estoque inicial**, como camada de ajuste sobre a
transferência: `106` mais `0` menos `2`. São ~8 movimentos por semana contra
~530 peças transferidas — correção de cerca de 1%, não estrutura. Mas sem eles
o número fica sistematicamente um pouco alto, porque o erro de envio entra e a
correção não.

### `TRANSFERÊNCIA DE ESTOQUE PA` (interno 4) — explicado em 20/09

2.013 movimentos em 2026, quarto maior evento do ano, ~39 por semana. Fica na
expedição, com a logística, e tem **três usos**, todos entre as lojas e o
e-commerce — nenhum deles traz peça de fora:

1. **Loja → e-commerce.** O Site não tem estoque: vendeu, a loja transfere a
   peça para ele faturar. É o mecanismo por trás da D12.
2. **Loja → loja.** A vendedora pede uma peça que está na outra loja.
3. **Loja → Bazar** (via e-commerce), quando o produto envelhece.

**Isso resolve a dúvida sem precisar medir: o evento 4 não entra no Estoque
inicial.** Ele não adiciona peça ao conjunto das lojas — movimenta dentro dele,
ou tira. A entrada continua sendo `106` mais `0` menos `2`.

Mas ele importa em dois outros pontos, e nos dois o risco é de errar para lados
opostos:

- **Loja → e-commerce não é perda de estoque.** A peça sai da loja porque *já
  foi vendida*, e essa venda já está contada no evento `25`. Tratar a
  transferência como baixa contaria a mesma peça duas vezes. Tem que ser
  ignorada.
- **Loja → Bazar é saída de verdade.** A peça deixa o universo do sellout. Se
  não for subtraída, o denominador guarda peça que não está mais em loja — e o
  sellout dos produtos antigos sai artificialmente baixo, justamente os que já
  estão sendo liquidados.

Ou seja: o evento 4 precisa ser lido **por destino**, e o destino mudar o sinal.
Sem isso, ou dobra venda, ou infla denominador.

`Lista_Por_Evento` traz `FILIAL` e `FILIAL_DESTINO` no documento e aceita
`EVENTO` — é o método para medir isso. Ainda não foi chamado para o `4`.

---

#### Histórico da investigação

**O que a lista de eventos mostrou (18/09):** `eventos/Eventos_InfluenciaEstoque`
devolveu 20 eventos, **todos de entrada** — o evento de saída "venda entre
filiais" não está lá. Isso melhora a situação em vez de piorar: o que forma o
Estoque inicial é a **entrada na loja**, e é justamente esse lado que o método
lista. Lendo pela entrada, o evento de venda nunca é tocado e não há risco de
inflar a receita de varejo.

Cinco candidatos, com um par revelador:

| evento | código | descrição |
|---:|---|---|
| 105 | `00107` | RECEBIMENTO DE COMPRA P.A **(LOJAS)** |
| 115 | `00123` | RECEBIMENTO ELENATIMES **(ATACADO)** |

O ERP já separa o que vai para loja do que vai para o atacado, no próprio
evento — exatamente o corte que o negócio descreve. Indício forte, não prova.
Os outros candidatos e a armadilha do código (`12` interno é devolução, `12` do
ERP é transferência) estão em `api-millennium.md`.

`coletor/explora_entradas.py` chama `Transferencia_Filiais` e
`saidas/MovimentacaoPorGrade` no mesmo período e mostra qual evento carrega
ELENA ES → lojas.

**A validar antes de confiar** — nada disso foi chamado ainda:

1. Puxar as transferências ELENA ES → lojas desde o início do acompanhamento e
   comparar o acumulado com a coluna Estoque inicial da planilha. Se bater, a
   coluna inteira vira dado.
2. Confirmar se toda entrada de loja passa por esse evento, ou se há entrada por
   outro caminho (compra direta, devolução de cliente, acerto de inventário).
   O que não passar por ele continua precisando de lançamento manual.
3. ~~Confirmar o tratamento de transferência **entre lojas**~~ — **confirmado em
   18/09: é realocação, não entrada.** Jardins → Iguatemi não cria peça nova no
   conjunto; só muda de prateleira. A regra: só entra no Estoque inicial a
   transferência cuja **origem está fora do conjunto de lojas** (ELENA ES). Com
   origem e destino ambos em loja, ignorar.

   Consequência prática: o Estoque inicial fica certo no total e certo por
   loja — mas o **sellout por loja** de um produto realocado fica torto, porque
   a peça foi vendida onde não nasceu. Como o sellout é acompanhado no
   consolidado, isso não morde hoje. Morderia se um dia houvesse sellout por
   filial.
4. Ver o que fazer com a produção que vai para o atacado e nunca chega às lojas:
   pela nova regra ela simplesmente não entra, o que parece certo.


## D14 · O Estoque inicial do produto novo vem do ERP, não da produção

Decidido em 20/09, como primeira aplicação prática da D13.

Quando a rodada insere um produto que ainda não tinha linha, ela precisa
inventar um Estoque inicial. A regra da D6 era `max(produção, estoque + vendas)`
— o melhor palpite disponível quando a produção era a única fonte.

**Agora existe fonte melhor.** O CSV que o coletor gera (evento 106, ELENA ES →
lojas) diz quantas peças de fato chegaram na loja, por produto e por cor. Com o
arquivo presente, é esse o número. Sem ele, vale a D6 e o relatório diz qual
regra foi usada em cada linha.

**Por que só no produto novo, por enquanto:** é a única hora em que o número
*nasce*. Para quem já tem linha, mudar o Estoque inicial significa reescrever um
saldo acumulado por meses — outra conversa, com outro risco. No produto novo não
há histórico a preservar: ou nasce certo, ou nasce errado e fica.

**O tamanho disso**, medido na rodada de 18/09 com as transferências de
31/08 a 07/09:

| código | ERP | produção | descrição |
|---|---:|---:|---|
| 334066 | 48 | 111 | BERMUDA PALA LINHO |
| 334044 | 52 | 106 | CAMISA SUMMER LINHO |
| 334128 | 34 | 86 | CALÇA SUMMER PREGAS LINHO |
| 334127 | 10 | 31 | BLAZER SUMMER BOX LINHO |
| 334037 | 29 | 50 | BLAZER SUMMER BOX LINHO |

Doze produtos, **502 peças pelo ERP contra 762 pela regra antiga**. O
denominador do sellout nasceria 52% maior, e o percentual, um terço menor —
justamente nos lançamentos, que é onde se decide repetir, aumentar ou cortar.

### Para onde vão as 260 peças de diferença

Medido contra o evento 108 (faturamento de atacado) na mesma semana:

| destino | peças | % da produção |
|---|---:|---:|
| lojas (evento 106) | 502 | 66% |
| atacado (evento 108) | 61 | 8% |
| ainda na Elena | 199 | 26% |

**O atacado é a menor parte.** A explicação intuitiva — "a produção inclui o
atacado" — está certa mas é secundária: só 8% saiu para cliente de atacado
naquela semana. Os outros 26% simplesmente **ainda não tinham sido
despachados** e estavam parados na Elena.

São dois motivos independentes para a produção não servir como Estoque inicial,
e o maior deles é de tempo, não de canal. Peça produzida na sexta e despachada
na terça seguinte não estava em loja nenhuma quando o sellout foi calculado.

Dois produtos confirmam isso ao contrário: `334017` recebeu 50 peças tendo
produzido 51, mas mandou 20 para o atacado — despachou 19 a mais do que produziu
na semana, de um lote anterior. `334096`, o mesmo, com 11. **Produção e
despacho não fecham por semana em nenhum produto**, e é por isso que uma coluna
nunca pôde substituir a outra, nem com ajuste.

**Como o arquivo chega:** o MN só responde dentro da rede da Egrey, então o app
na nuvem nunca vai buscá-lo. O coletor puxa lá e o CSV sobe junto com as
planilhas, num campo opcional da primeira tela.

```
python -m coletor.estoque_inicial --de 2026-01-01 --ate 2026-09-07 \
    --para-app entradas-erp.csv
```

**Se for revista:** o passo seguinte natural é o incremento semanal — hoje a
rodada soma a aba Producao ao Estoque inicial de quem já tem linha (D5). Pela
mesma lógica, deveria somar a transferência. Fica para depois de a conferência
fechar, porque ali há histórico em jogo.
