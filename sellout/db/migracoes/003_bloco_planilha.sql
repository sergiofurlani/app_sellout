-- Onde o produto está classificado na planilha, hoje.
--
-- É uma foto de transição, e o nome da coluna diz isso: `bloco_planilha`.
-- A partir do momento em que o cadastro do ERP estiver arrumado, a coleção
-- vem só de lá (`produto.colecao`) e esta coluna deixa de ser consultada —
-- mas continua servindo de registro do que era antes.
--
-- Por que gravar em vez de só comparar uma vez: enquanto o cadastro está
-- sendo corrigido, os dois convivem. Ter a classificação antiga guardada é o
-- que permite dizer, produto a produto, o que mudou e por quê — em vez de
-- descobrir meses depois que um bloco inteiro trocou de lugar sem registro.
ALTER TABLE produto ADD COLUMN IF NOT EXISTS bloco_planilha text;

-- Quando a foto foi tirada. Bloco sem data não diz se está velho.
ALTER TABLE produto ADD COLUMN IF NOT EXISTS bloco_em date;

CREATE INDEX IF NOT EXISTS produto_bloco ON produto (bloco_planilha);
