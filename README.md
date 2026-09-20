# Sellout semanal — E.GREY

Automatiza a atualização semanal das planilhas **sellout geral** e **Sellout Clássicos**
a partir das abas de origem da planilha geral (Estoque, Vendas, Producao, Preco e Produtos).

A rodada tem três telas: enviar as planilhas, conferir o que precisa de decisão e baixar os
arquivos. Nada é gravado sem passar pela tela de conferência.

## O que a rodada faz

1. **Rotação da coluna de sellout** — cria a coluna nova com a data da rodada e congela o
   percentual da semana anterior na coluna ao lado, como valor fixo. Todo o histórico à
   direita é deslocado junto.
2. **Estoque atual** — substitui pela soma das linhas da aba Estoque, nas filiais escolhidas.
3. **Vendas** — soma as quantidades da aba Vendas às colunas Jardins, Iguatemi e Site.
4. **Divisão por cor** — quando o mesmo código ocupa duas linhas, o trecho escrito em
   **vermelho** ao final da descrição diz de quais cores aquela linha trata; a linha sem
   vermelho fica com o restante. `DEMAIS CORES` também significa o restante. A comparação
   ignora acentos e resolve abreviações (`OFF` → `OFF-WHITE`, `AMARELA` → `AMARELO`).
5. **Produção** — soma a quantidade da aba Producao no Estoque inicial, anexando à fórmula
   existente (`=24+28` vira `=24+28+5`) para preservar o rastro. Por padrão só entra em
   produto que tenha estoque atual.
6. **Produtos novos** — códigos da aba Produtos que ainda não existem nas planilhas entram ao
   final do bloco da sua coleção, com as fórmulas replicadas. O bloco é encontrado pelo nome
   da coleção na coluna C, então funciona sozinho quando a coleção virar.
7. **Fórmulas** — refaz os subtotais de cada bloco e o total geral depois do deslocamento das
   linhas, e recalcula o **Nível de Estoque** cruzando a aba Estoque com a aba Preco por
   Código + Código Cor + Tamanho.

Ao final sai também um **relatório de conferência** com o que foi feito e o que ficou pendente.

## Decisões da tela de conferência

| Decisão | Padrão |
|---|---|
| Nome da coluna de sellout | `Sellout dd/mm` de hoje |
| Filiais do estoque | todas as encontradas no arquivo da semana |
| Produção só com estoque atual | ligado |
| Códigos duplicados que o vermelho não resolve | manter as linhas como estão |
| Produtos novos | marcados os que têm estoque |

## Documentação

| Documento | Para quê |
|---|---|
| [docs/arquitetura.md](docs/arquitetura.md) | como o sistema é hoje e para onde vai |
| [docs/decisoes.md](docs/decisoes.md) | as regras de negócio e por que cada uma existe |
| [docs/roteiro.md](docs/roteiro.md) | as etapas da migração para banco e os pontos em aberto |
| [docs/operacao.md](docs/operacao.md) | rodada semanal, o que conferir e como voltar atrás |
| [docs/api-millennium.md](docs/api-millennium.md) | acesso ao ERP, armadilhas verificadas e o que falta descobrir |
| [docs/eventos-mn.md](docs/eventos-mn.md) | os 57 eventos de estoque do ERP e quais entram no sellout |

A tag `v1.0` marca o processo por planilha funcionando e conferido — é o ponto
de retorno caso a migração para banco não dê certo.

## Rodar localmente

```bash
pip install -r requirements.txt
uvicorn sellout.web.main:app --reload
```

Pelo terminal, sem subir o app:

```bash
python -m sellout.cli "sellout geral.xlsx" "Sellout Clássicos.xlsx" -s saida/
python -m sellout.cli geral.xlsx classicos.xlsx --so-analisar   # só o diagnóstico, em json
```

Testes:

```bash
python -m pytest
```

## Deploy

Feito para Railway (Nixpacks). O start command está em `railway.json`; o healthcheck responde
em `/saude`.

Variáveis opcionais:

| Variável | Padrão | Para quê |
|---|---|---|
| `SELLOUT_WORKDIR` | `/tmp/sellout-jobs` | pasta de trabalho das rodadas |
| `SELLOUT_TTL_HORAS` | `6` | por quanto tempo os arquivos ficam disponíveis |
| `SELLOUT_MAX_MB` | `60` | tamanho máximo de cada upload |

Os arquivos enviados e gerados ficam só em disco temporário e são apagados depois do TTL —
não há banco de dados nem persistência entre rodadas.

## Organização

```
sellout/core/cores.py      normalização e casamento de nomes de cor
sellout/core/leitura.py    leitura das abas de origem e da estrutura de blocos
sellout/core/divisao.py    divisão de um código entre linhas pelo texto em vermelho
sellout/core/motor.py      análise e processamento da rodada
sellout/core/relatorio.py  relatório de conferência
sellout/web/               app FastAPI (3 telas)
sellout/cli.py             execução pelo terminal
coletor/mn.py              cliente da API Millennium (roda na rede da Egrey)
coletor/valida_site.py     compara a venda por filial do MN com a planilha
coletor/explora_entradas.py descobre por qual evento a peça entra no estoque da loja
coletor/estoque_inicial.py  Estoque inicial pela venda entre filiais (evento 106)
```
