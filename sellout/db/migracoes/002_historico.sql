-- O histórico que mora nas colunas de sellout das abas de trabalho.
--
-- São 171 semanas no Masculino (desde 04/12/2022) e 45 no Feminino. Cada
-- coluna à direita da K é uma rodada, com a data no cabeçalho e o percentual
-- na célula.
--
-- Por que tabela própria, e não `snapshot`: dessas colunas só sobrou o
-- **resultado**. Vendas, estoque e estoque inicial daquela semana não foram
-- guardados — a planilha sobrescrevia. Gravar isto como snapshot fingiria uma
-- medição que não existe. Aqui é o que é: um percentual histórico, sem o que
-- o produziu.
--
-- `cores` separa as duas linhas de um código dividido pelo texto em vermelho
-- (D1): a linha da cor específica e a linha do resto têm percentuais
-- diferentes e são registros diferentes. Vazio é a linha sem vermelho.

CREATE TABLE IF NOT EXISTS sellout_historico (
    planilha      text NOT NULL CHECK (planilha IN ('geral', 'classicos')),
    aba           text NOT NULL,
    codigo        text NOT NULL,
    cores         text NOT NULL DEFAULT '',
    data          date NOT NULL,
    percentual    numeric NOT NULL,
    bloco         text,
    colecao       text,
    descricao     text,
    carregado_em  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (planilha, aba, codigo, cores, data)
);

CREATE INDEX IF NOT EXISTS sellout_historico_codigo ON sellout_historico (codigo, data DESC);
CREATE INDEX IF NOT EXISTS sellout_historico_data ON sellout_historico (data DESC);
