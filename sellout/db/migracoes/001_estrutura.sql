-- Estrutura inicial. Modelo descrito em docs/arquitetura.md.
--
-- Três camadas, e a separação entre elas é o ponto:
--
--   dimensões   o que as coisas são           muda devagar, sem snapshot
--   fatos       o que foi medido na semana    imutável depois de gravado
--   saldo       o que é conhecimento nosso    saldo de abertura + movimentos
--
-- O que torna isto diferente da planilha: a saída de uma semana nunca é a
-- entrada da seguinte. Cada snapshot é um retrato do que a origem disse
-- naquele dia, e o sellout é consulta sobre eles. Defeito não se propaga.

-- ---------------------------------------------------------------- dimensões

CREATE TABLE IF NOT EXISTS produto (
    codigo        text PRIMARY KEY,
    descricao     text,
    divisao       text,
    departamento  text,
    grupo         text,
    marca         text,
    grade         text,
    colecao       text,
    -- D11: linha comercial (HOME, GLORIA KALIL, PIMA, CASHMERE, COURO) não
    -- existe como campo no ERP. Hoje é o nome do bloco na planilha; aqui vira
    -- atributo nosso, editável.
    linha         text,
    criado_em     timestamptz NOT NULL DEFAULT now(),
    alterado_em   timestamptz NOT NULL DEFAULT now()
);

-- O código de cor é global: 68 códigos, nenhum com dois nomes. `0002` é PRETO
-- em qualquer produto — por isso é dimensão de verdade, não texto repetido.
CREATE TABLE IF NOT EXISTS cor (
    codigo_cor    text PRIMARY KEY,
    nome          text NOT NULL
);

CREATE TABLE IF NOT EXISTS produto_cor (
    codigo        text NOT NULL REFERENCES produto(codigo) ON DELETE CASCADE,
    codigo_cor    text NOT NULL REFERENCES cor(codigo_cor),
    PRIMARY KEY (codigo, codigo_cor)
);

CREATE TABLE IF NOT EXISTS filial (
    codigo        text PRIMARY KEY,
    nome          text,
    -- o papel decide onde a filial entra, e é diferente por fonte (D12):
    -- loja entra em estoque e vendas; ecommerce só em vendas; matriz só como
    -- origem das peças; fora não entra em lugar nenhum.
    papel         text NOT NULL DEFAULT 'fora'
                  CHECK (papel IN ('loja', 'ecommerce', 'matriz', 'fora'))
);

-- ------------------------------------------------------------------- fatos

CREATE TABLE IF NOT EXISTS snapshot (
    id            bigserial PRIMARY KEY,
    data          date NOT NULL,
    origem        text NOT NULL CHECK (origem IN ('upload', 'erp')),
    quem          text,
    observacao    text,
    criado_em     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS snapshot_data ON snapshot (data DESC);

CREATE TABLE IF NOT EXISTS estoque (
    snapshot_id   bigint NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    codigo        text NOT NULL,
    codigo_cor    text NOT NULL,
    tamanho       text NOT NULL,
    filial        text NOT NULL,
    qtd           numeric NOT NULL,
    PRIMARY KEY (snapshot_id, codigo, codigo_cor, tamanho, filial)
);

CREATE TABLE IF NOT EXISTS venda (
    snapshot_id   bigint NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    codigo        text NOT NULL,
    codigo_cor    text NOT NULL,
    tamanho       text NOT NULL,
    filial        text NOT NULL,
    qtd           numeric NOT NULL,
    valor         numeric,
    PRIMARY KEY (snapshot_id, codigo, codigo_cor, tamanho, filial)
);

CREATE TABLE IF NOT EXISTS producao (
    snapshot_id   bigint NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    codigo        text NOT NULL,
    codigo_cor    text NOT NULL,
    tamanho       text NOT NULL,
    qtd           numeric NOT NULL,
    PRIMARY KEY (snapshot_id, codigo, codigo_cor, tamanho)
);

CREATE TABLE IF NOT EXISTS preco (
    snapshot_id   bigint NOT NULL REFERENCES snapshot(id) ON DELETE CASCADE,
    codigo        text NOT NULL,
    codigo_cor    text NOT NULL,
    tamanho       text NOT NULL,
    preco         numeric NOT NULL,
    PRIMARY KEY (snapshot_id, codigo, codigo_cor, tamanho)
);

-- ------------------------------------------------------------------ saldo

-- D10: o valor de hoje, congelado numa data-base. É o único número que entra
-- sem vir do ERP — a herança daquelas fórmulas `=86-1+44-2`.
CREATE TABLE IF NOT EXISTS saldo_abertura (
    codigo        text NOT NULL,
    codigo_cor    text NOT NULL,
    data_base     date NOT NULL,
    qtd           numeric NOT NULL,
    origem        text NOT NULL DEFAULT 'planilha',
    PRIMARY KEY (codigo, codigo_cor, data_base)
);

-- D13: dali em diante a entrada é derivada do ERP, com data, produto, cor e
-- tamanho. `tipo` guarda POR QUE a peça se moveu, porque o mesmo evento muda
-- de sinal conforme o destino:
--
--   transferencia   ELENA ES -> loja, evento 106. É o Estoque inicial.
--   devolucao       loja -> ELENA ES, evento 106 ao contrário.
--   ajuste          eventos 0 e 2, correção de erro de envio.
--   realocacao      evento 4 entre lojas: soma zero no consolidado.
--   saida_bazar     evento 4 para o Bazar: sai do universo do sellout.
--   manual          lançado por gente, com observação obrigatória.
--
-- O evento 4 para o e-commerce NÃO entra aqui: a peça sai da loja porque já
-- foi vendida, e a venda já está contada. Registrar seria contar duas vezes.
CREATE TABLE IF NOT EXISTS movimento (
    id            bigserial PRIMARY KEY,
    data          date NOT NULL,
    codigo        text NOT NULL,
    codigo_cor    text NOT NULL,
    tamanho       text,
    filial        text,
    tipo          text NOT NULL CHECK (tipo IN (
                      'transferencia', 'devolucao', 'ajuste',
                      'realocacao', 'saida_bazar', 'manual')),
    qtd           numeric NOT NULL,
    evento_mn     integer,
    documento     text,
    observacao    text,
    snapshot_id   bigint REFERENCES snapshot(id) ON DELETE SET NULL,
    criado_em     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS movimento_chave ON movimento (codigo, codigo_cor, data);

-- Um movimento do ERP não pode entrar duas vezes se a extração for repetida.
-- Movimento manual não tem documento, então fica de fora do índice.
CREATE UNIQUE INDEX IF NOT EXISTS movimento_unico_erp
    ON movimento (documento, evento_mn, codigo, codigo_cor, tamanho, filial)
    WHERE documento IS NOT NULL;
