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

Descobrir o código do evento é o primeiro passo — `eventos/Eventos_InfluenciaEstoque`,
sem parâmetro, lista todos com código e descrição. Com ele na mão, decidir entre
`transferencias/Transferencia_Filiais` (tem `SCRIPTEVENTO`) e
`movimentacao/vendas_consulta_completa` filtrando por esse `EVENTO`. Detalhes em
`api-millennium.md`.

**A validar antes de confiar** — nada disso foi chamado ainda:

1. Puxar as transferências ELENA ES → lojas desde o início do acompanhamento e
   comparar o acumulado com a coluna Estoque inicial da planilha. Se bater, a
   coluna inteira vira dado.
2. Confirmar se toda entrada de loja passa por esse evento, ou se há entrada por
   outro caminho (compra direta, devolução de cliente, acerto de inventário).
   O que não passar por ele continua precisando de lançamento manual.
3. Confirmar o tratamento de transferência **entre lojas** — Jardins → Iguatemi
   não é entrada nova no conjunto, só realocação.
4. Ver o que fazer com a produção que vai para o atacado e nunca chega às lojas:
   pela nova regra ela simplesmente não entra, o que parece certo.
