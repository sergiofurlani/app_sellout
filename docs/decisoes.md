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

**Achado em 21/09, e é grave: a `sellout geral.xlsx` de hoje não tem nenhum
texto em vermelho.** Zero células com formatação rica nas duas abas de
trabalho; o único vermelho que sobrou está nos títulos dos blocos
(`MASCULINO - SS27`, `FEMININO - HOME`), que é decoração e não regra. Ou seja,
**a D1 está sem entrada** — todo código em duas linhas virou ambiguidade, que é
exatamente o que a conferência acusou em 14 códigos.

Bate com o incidente registrado na D9: uma rodada apagou o vermelho, e ele
nunca foi reposto. O `coletor/monta_fontes.py` mede isso antes e depois de
escrever, mas a medida hoje parte de zero — não há mais o que perder, e sim o
que restaurar. Enquanto não voltar, a divisão por cor depende do cadastro do
ERP (D11), que resolve parte dos casos, e do olho de quem confere.

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

**Decidido em 21/09: congelar menos do que a D10 dizia.** A coluna da planilha
é por *linha de produto*; o banco trabalha por produto **e cor**. Repartir o
número da linha entre as cores seria estimativa nossa virando número guardado —
e número guardado ninguém desfaz seis meses depois. O corte passa a ser por
data:

- **AW26 e SS27 não são congeladas.** São reconstruídas pelos movimentos do
  evento 106 desde 01/01/2026, com cor e tamanho de verdade. A conferência de
  21/09 sustenta: AW26 bate em 97% das linhas dentro de ±10 peças, e no SS27,
  quando planilha e ERP discordam, quem costuma estar certo é o ERP — a
  planilha guardou produção, não chegada (D14).
- **O resto é congelado por produto, sem cor.** São coleções antigas em
  liquidação: o total ainda importa para o percentual, a divisão por cor já não
  decide nada.
- **Código que aparece nos dois lados fica inteiro com o ERP.** Congelar a
  metade antiga e deixar o ERP somar a dele contaria o produto duas vezes.

Na planilha de 21/09: **106 produtos e 11.261 peças congelados**, 89 produtos e
4.070 peças reconstruídos. `sellout/db/abertura.py` faz o congelamento e
`sellout/db/movimentos.py` carrega os movimentos do coletor; os dois só gravam
com `--aplicar`, e a coluna `origem` diz de onde veio cada número.

## D11 · A linha comercial é dado nosso — a coleção não

**Revisto em 20/09.** Metade desta decisão estava errada.

**A coleção É campo do cadastro do ERP.** O `334128` é coleção VERÃO,
subcoleção 2027; o bloco `SS27` da planilha é a mesma informação escrita de
outro jeito. `produtosac/Lista` devolve `DESC_COLECAO` e `DESC_SUBCOLECAO` por
produto, junto com tipo, grupo, departamento, marca, divisão e categoria — as
dimensões que a tela nova precisa para filtrar (D9), todas de graça.

A sigla é montada em `coletor/produtos.py`: estação pela coleção (VERÃO → `SS`,
INVERNO → `AW`) e ano pelos dois últimos dígitos da subcoleção. É o único ponto
onde o vocabulário do ERP encontra o da planilha, e está isolado de propósito.

**O que continua sendo nosso:** HOME, GLORIA KALIL, PIMA, CASHMERE, COURO — a
linha comercial. Esses blocos não têm correspondente no cadastro e seguem sendo
atributo do produto, editável no app.

**O que isso destrava:** código que aparece em dois blocos — `330043` está em
AW26 e SS27 — deixa de ser ambiguidade. O cadastro diz `AW26`, a linha daquele
bloco fica com a transferência e a outra é marcada como sobra de bloco antigo,
em vez de aparecer zerada como se faltasse peça.

**Onde o cadastro não resolve:** o `328028` está nos mesmos dois blocos e o
cadastro diz `SS24` — nenhum dos dois. Aí não há desempate, e a conferência diz
isso na coluna Obs em vez de escolher uma linha por sorteio. Quem diverge é a
planilha; o cadastro respondeu.

**Categorização é o cadastro; descrição é descrição.** O nome do produto não
categoriza nada. `CAMISA CLÁSSICA` no nome não põe o produto na linha
Clássicos, e esse produto não está em Clássicos. Deduzir categoria pelo nome já
deu errado aqui antes — foi assim que "sapato e tricô entram por compra" virou
conclusão a partir de seis nomes de produto, e estava errado.

Confirmado no cadastro: 3.976 produtos, e a coleção só vira sigla quando é
estação com ano. `ATEMPORAL`, `PERENE` e `INDEFINIDO` não são estação e nunca
vão virar `SS27` — estão em `SEM_ESTACAO` para não parecerem mapa faltando.

**Os Clássicos são a coleção `PERENE`, e só ela.** Não `ATEMPORAL`, que é
outra coisa. É a regra que define o universo da *Sellout Clássicos*: em vez de
lista mantida à mão, o cadastro responde quem entra. São 28 produtos hoje.

## D12 · O e-commerce não tem estoque próprio

O Site vende do estoque das lojas. Então a filial do e-commerce entra em
**vendas** e fica de fora de **estoque** — contá-la duplicaria o saldo das lojas.

**A filial do e-commerce é a `00044`** — interno `105` na tabela de filiais, que
colide com o evento `105`; dois números iguais, coisas diferentes. Ela recebe
por transferência produto antigo que foi para o Bazar, e **esse saldo não conta
como estoque**. Em 2026 entraram nela 139 peças em 36 documentos: pouco, e
justamente o tipo de resíduo que reapareceria mais tarde como diferença sem
explicação. Regra dada pelo negócio em 20/09.

As cinco filiais que existem: `104 EGREY JDS`, `5 IGUATEMI`, `105 00044`
(e-commerce), `102 ELENA ES`, `101 ELENA SP`. O resto da tabela é cadastro
antigo.

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
| atacado já faturado (evento 108) | 61 | 8% |
| parado na Elena | 199 | 26% |

**As 199 peças paradas na Elena são estoque de atacado**, esperando
faturamento — não são peças a caminho das lojas. Explicado pelo negócio em
20/09, e é o que corrige a leitura errada que este documento chegou a ter:
eu havia classificado essa sobra como "ainda não despachada", como se fosse
virar estoque de loja mais tarde. Não vira.

Então a divisão é limpa: **das 762 peças produzidas, 502 são varejo e 260 são
atacado** — 61 já faturadas e 199 ainda em estoque. A explicação simples, a que
o negócio deu desde o começo, estava certa: a produção inclui o atacado, e por
isso não serve como Estoque inicial de loja.

O que continua valendo da leitura por tempo é menor, mas real: produção e
despacho não fecham na mesma semana. `334017` recebeu 50 peças tendo produzido
51 e mandado 20 para o atacado — despachou 19 a mais do que produziu, de um
lote anterior; `334096`, o mesmo, com 11. Por isso nenhum desconto aplicado
sobre a coluna de produção resolveria: seria preciso saber **quando** cada peça
saiu, e só a transferência tem isso.

### A conferência de 9 meses: 1,5% no total, 0,5% no AW26

Janela de 01/01 a 20/09, 1.080 documentos, 16.975 peças.

| | planilha | ERP | |
|---|---:|---:|---|
| AW26 (155 produtos) | 7.927 | 7.964 | **+0,5%** |
| SS27 (54 produtos) | 2.799 | 2.601 | −7,1% |
| **total** | **10.726** | **10.565** | **−1,5%** |

De 209 produtos, **78 batem exato** e outros 76 ficam dentro de 5%.

**O AW26 fecha.** Uma coluna mantida à mão por nove meses reproduz o ERP com
meio por cento de erro em 155 produtos. A derivação da D13 está certa e a coluna
também estava.

**O que sobra no SS27 é a D14 se mostrando**, não falta de dado:

| código | planilha | ERP | |
|---|---:|---:|---|
| 334128 | 86 | 34 | 86 é a produção |
| 334155 | 64 | 24 | |
| 334069 | 139 | 100 | |

São produtos novos cujo Estoque inicial nasceu de `max(produção, …)` — a regra
antiga. O ERP diz quanto chegou na loja; a planilha guardou quanto foi
produzido. É exatamente o erro que a D14 corrige na origem.

**E dois casos que eram defeito meu:** `328028` e `330043` aparecem em AW26
**e** SS27, sem vermelho em nenhuma das linhas. A regra do "resto" jogava todo o
saldo na última linha e deixava a outra zerada — 107 peças de falso buraco. O
ERP tem um único fluxo por código e não reparte peça entre linhas — repartir
seria invenção nossa. Com o cadastro (D11), o `330043` passou a ter desempate:
é AW26, a linha daquele bloco fica com tudo. O `328028` continua sem, porque o
cadastro diz SS24 e nenhuma das duas linhas é SS24. Nos dois casos o total vai
numa linha só, com a observação dizendo por quê.

Descontando essas 107, a diferença real é de **54 peças em 10.726 — 0,5%**.

### O que parecia faltar e não faltava (20/09, período cheio de 2026)

Com o cadastro classificando, a conferência de 01/01 a 20/09 acusou 66 produtos
"da coleção, sem linha na planilha", 3.302 peças, e 49 "fora das coleções",
3.108 peças. Conferido código a código contra a planilha inteira:

| | produtos | peças | o que é |
|---|---:|---:|---|
| tem linha, em bloco de linha comercial | 37 | 2.110 | HOME, GLORIA KALIL, PIMA, CASHMERE, COURO |
| sem linha em lugar nenhum | 29 | 1.192 | 1.113 são SS27, coleção entrando agora |
| PERENE = Clássicos | 24 | 2.748 | outra planilha |
| coleção sem subcoleção no cadastro | 21 | 273 | 18 VERÃO, 3 INVERNO — sem ano, sem sigla |
| sem coleção nenhuma no cadastro | 2 | 85 | |

Das 1.832 peças de AW26 que apareceram como pendentes, **1.753 já tinham
linha** — estavam na linha comercial. Sobram 79. O pendente real de AW26 é
ruído; o de SS27 é a coleção chegando.

**O que isso deixa em aberto:** 18 produtos de VERÃO sem subcoleção no
cadastro, 270 peças. Sem o ano não há sigla, e sem sigla eles não pousam em
bloco nenhum. Se algum for SS27, é preenchimento que falta no ERP — e é
invisível hoje.

### Nem tudo entra pela Elena: o sapato vem por compra direta

Corrigido pelo negócio em 20/09, depois de duas idas e vindas que vale registrar
porque o erro foi de método:

- **Tricô é produção própria.** Compra-se o fio, manda-se tecer, depois costurar.
  Entra pela Elena, evento `106`, como o resto.
- **Sapato não passa pela Elena.** Entra direto na loja pelo
  `105 RECEBIMENTO DE COMPRA P.A (LOJAS)` — 922 movimentos em 2026, o maior
  evento de entrada do ano.

**O 105 é o outro lado do 106 — resolvido em 21/09.** A consulta direta ao
banco do ERP trouxe os 922 documentos do evento em 2026 (**16.384 peças**,
contra 16.975 do 106) e depois os 6.540 itens deles. O casamento não deixa
dúvida:

| | |
|---|---|
| produtos no 105 | 306 |
| desses, presentes também no 106 | **305** |
| com quantidade **idêntica** nos dois | 198 |
| exclusivos do 105 | 1 produto, 1 peça |
| `FORNECEDOR` dos documentos | `559` em 917 dos 922 (16.323 das 16.384 peças) |

Uma transferência entre as empresas tem dois lançamentos: a Elena **fatura**
(`106 VENDAS ENTRE FILIAIS`, saída) e a loja **recebe** (`105 RECEBIMENTO DE
COMPRA P.A (LOJAS)`, entrada). Mesma peça, dois eventos, um movimento físico.
As diferenças que sobram são de ±1 a ±6 peças — documento emitido num mês e
recebido no outro.

**Consequência: somar 105 e 106 dobraria o Estoque inicial.** A D14 fica como
está, lendo só o `106`. E a tensão registrada em 20/09 se desfaz sozinha: o
AW26 fechar com +0,5% usando só um dos lados é exatamente o que se espera de
dois lançamentos do mesmo movimento.

**O que eu errei aqui.** Você disse "os sapatos não passam pela Elena e entram
pelo evento recebimento de compra p.a. (lojas)" — verdade do ponto de vista
comercial, a peça é comprada e não produzida. Eu transformei isso em "existe um
canal paralelo que o Estoque inicial não vê" e passei quatro rodadas de API
atrás dele. O canal não existe; o que existe é o mesmo movimento escriturado
dos dois lados.

**Confirmado pelo negócio em 21/09: o `FORNECEDOR 559` é a ELENA ES.** A loja
compra da Elena; a Elena fatura para a loja. Os dois lançamentos têm as duas
pontas do mesmo par, e o assunto está fechado.

**A regra que sai daí, e vale para todo evento novo:** antes de somar um evento
ao Estoque inicial, conferir se ele não é a contrapartida de outro que já está
na conta. O par se reconhece assim — mesmos produtos, mesmas quantidades,
mesmo cliente/fornecedor dos dois lados. Um evento de entrada e um de saída com
o mesmo conteúdo são um movimento, não dois.

**Os sapatos de SS27 ainda não chegaram.** Os 13 que eu tinha dado como "buraco
do 105" não aparecem em nenhum dos dois eventos: `239065`, `239066`, `239069`,
`239082`, `334119` a `334122`, `334159`, `336012`, `336013` e os dois com
sufixo `ERR` no código (`239067ERR`, `239068ERR` — sujeira de cadastro, e quem
casa planilha e ERP pelo código não acha esses). Não é leitura faltando: é
coleção que está entrando agora. O `239067`, que chegou dia 14, aparece com 15
peças.

**O que o 105 mostra de verdade**, por ser o lado da entrada e trazer a filial
de destino sem ambiguidade:

| destino | peças |
|---|---:|
| 104 EGREY JDS | 9.894 |
| 5 IGUATEMI | 6.282 |
| 105 00044 (e-commerce, Bazar — não conta estoque) | 139 |
| ELENA ES / ELENA SP / 00040 | 69 |

E por coleção, nas lojas: AW26 8.937, SS27 3.418, PERENE 2.919 (Clássicos),
o resto abaixo de 300. Calçado inteiro: 492 peças em 14 produtos — 3% do total.
O 105 nunca foi sobre sapato.

**O obstáculo técnico que deixou de importar:** `vendas_consulta_completa` não
enxerga evento de entrada, e o `Lista_Por_Evento` não respondeu nem ao `106` no
teste de controle. Gastei quatro rodadas no `saidas/MovimentacaoPorGrade`, que
é relatório e cobra `QUEBRA` — booleano, aliás, e o erro de SQL que ele devolvia
era o `SCRIPTEVENTO`, não o `QUEBRA`. Uma consulta ao banco do ERP resolveu em
dois arquivos. `coletor/sonda_parametros.py` fica para o próximo método que
cobrar parâmetro não publicado; a lição é outra: **quando existe acesso ao banco,
perguntar ao banco primeiro.**

### A janela da extração tem que alcançar a planilha (20/09)

A primeira conferência de 9 meses parou em 07/09 e mostrou nove produtos do
SS27 com ERP zerado — 457 peças, 80% do desvio da coleção. Três eram sapatos e
três eram tricôs, e eu concluí que produto comprado entraria por outro evento.

**Errado, nas duas pontas.** O sapato também vai da Elena para as lojas, e o
tricô é produção própria: compra-se o fio, manda-se tecer e depois costurar.
Não há caminho de entrada alternativo para eles.

O que havia era mais simples: **o `334069` chegou na loja em 12/09 e o `239067`
em 14/09**, depois do fim da janela. A planilha, atualizada em 18/09, já contava
essas peças; a extração, não. O zero não era divergência, era recorte.

Por isso `--ate` passa a valer **hoje** por padrão, e uma data anterior à de
hoje dispara aviso. Numa semana de lançamento chega produto novo toda hora, e
uma janela curta transforma chegada recente em falsa divergência — o tipo de
erro que faz alguém desconfiar do número certo.

**A validar quando a extração de 9 meses rodar:** se nenhuma das 199 peças
aparecer num evento 106 posterior, a regra está confirmada e o corte é
definitivo — `106` é varejo, todo o resto é atacado. Se aparecer, existe um
caminho de Elena para loja com atraso, e o Estoque inicial precisa acompanhar a
data em vez de fechar por semana.

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

## D15 · O evento 207 é devolução para a Elena — sai do estoque, não da venda

Em setembro/2026 a Egrey criou o evento **207** (`00210`,
`DEVOLUÇÃO PARA ELENATIMES`) para a loja devolver peça que não vendeu. A
primeira vez que ele apareceu foi na devolução recente da Jardins, e é o que
explicava as devoluções que faltavam na comparação da semana de 14 a 20/09:
**todas eram da EGREY JDS**.

O export de vendas do ERP traz esse evento como **venda negativa**, e foi por
aí que ele entrou na conversa. Mas a peça nunca foi vendida: ela saiu da loja e
voltou para a Elena.

**Decidido pelo negócio em 21/09: entra como saída de estoque.** Abate o
**Estoque inicial**, não a Venda.

A diferença não é cosmética. Contar como venda encolheria o numerador e
deixaria o denominador intacto — erro dos dois lados, num indicador que é
razão. Como saída de estoque, o denominador cai junto com a peça que saiu, que
é o que de fato aconteceu.

**Onde isso vive no código:** `coletor/conferencia.py` e
`coletor/estoque_inicial.py` passam a puxar `EVENTOS = (106, 207)`. A lógica de
direção já existente (`_matriz`, `LOJAS`) reconhece loja → Elena como `sinal =
-1`, então o 207 subtrai sem nenhum tratamento especial. `coletor/vendas.py`
**não** o inclui, de propósito.

O volume hoje é pequeno — evento recém-criado, uma devolução só —, então a
conferência de 9 meses praticamente não se move. O valor da mudança é a partir
de agora: quando a loja devolver de novo, o estoque acompanha sozinho.

## D16 · A janela vai até ontem, e o teto de sanidade é por semana

Duas correções que saíram da primeira rodada de 9 meses com o 207 incluído.

### O dia de hoje não entra

A D14 tinha empurrado `--ate` para **hoje**, para que produto recém-chegado não
aparecesse com ERP zerado. Foi longe demais: **hoje é um dia pela metade**. A
peça que chega às 17h está na rodada da tarde e não estava na da manhã, e o
mesmo comando passa a devolver dois Estoques iniciais diferentes no mesmo dia.
Pior, o número não fecha com a planilha, que é fechada por dia.

`--ate` passa a valer **ontem**, o último dia fechado, em `conferencia.py` e em
`estoque_inicial.py` — uma definição só, importada, porque as duas precisam da
**mesma** janela: se divergirem, uma acusa divergência que a outra criou.

O aviso de janela curta também passa a comparar com ontem. Comparando com hoje,
a rodada certa avisava sempre — e aviso que aparece sempre deixa de ser lido.

### O teto de produção era de uma semana

O rodapé trazia `TETO_PRODUCAO = 826`, peça acabada da aba Producao, comparado
direto com o líquido do período. Era um número de **uma semana**, e na rodada de
9 meses ele acusou `ESTOUROU. A leitura esta errada.` contra 17.000 peças — que
é o número certo. O alarme comparava 38 semanas de transferência com a produção
de uma.

Agora o teto é **por semana**, multiplicado pelas semanas da janela, com folga
de 2x. As mesmas 17.000 peças dão 55% da produção do período, que é uma
proporção plausível: a produção chega inteira na Elena, varejo e atacado juntos
(D13), e só parte vira transferência para loja.

**O que esse teto é:** ordem de grandeza, para pegar leitura duplicada ou
evento a mais na lista. Não é auditoria, e o texto passa a dizer isso.

## D17 · Gravar a planilha pelo openpyxl apaga uma semana de histórico

Em 21/09 a rodada saiu com a coluna **`Sellout 14/09` em branco**. A `21/09`
apareceu certa; a anterior, que deveria ter sido congelada com o valor da
semana, veio vazia.

**A causa:** o openpyxl não calcula fórmula, e ao salvar descarta o resultado
que o Excel tinha guardado em cada célula. O `monta_fontes` abria a planilha
inteira, escrevia as abas de origem e salvava — e nisso apagou o valor guardado
das 1.598 fórmulas das abas de trabalho.

O app congela a coluna da semana passada lendo justamente esse valor:

```python
cache_sellout = {r: ws_val.cell(r, col_sellout).value ...}   # data_only=True
```

Achou `None` e escreveu vazio. **Nada acusou** — o arquivo abre, as fórmulas
estão lá, e o Excel recalcula ao abrir. Só quem lê por programa vê o buraco.

**A correção:** o `.xlsx` passa a ser tratado como o zip que é
(`coletor/planilha_xml.py`). Cada parte é copiada byte a byte e só o XML das
três abas de dados é trocado. As abas de trabalho não são lidas nem
reescritas — chegam do outro lado idênticas, com o valor guardado, o vermelho
da D1 e a formatação. Conferido na planilha real: **5.379 células das abas de
trabalho iguais, zero diferentes**, e as 1.598 fórmulas com valor intactas.

Os textos das abas novas vão como `inlineStr`, não pela tabela de textos
compartilhados: assim uma aba trocada não depende de índices que pertencem às
outras.

**A guarda que faltava:** o `monta_fontes` já contava o texto em vermelho antes
e depois. Passa a contar também as fórmulas com valor guardado, e se o número
cair ele recusa o arquivo. Era a metade da integridade que ninguém media.

**Lição que vale além deste caso:** biblioteca que reescreve um formato rico
devolve *quase* o mesmo arquivo, e o que ela perde no caminho não aparece na
tela. Quando só uma parte precisa mudar, trocar só aquela parte é mais seguro
do que reescrever tudo — mesmo custando mais código.
