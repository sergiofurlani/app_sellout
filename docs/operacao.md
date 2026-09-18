# Operação

## Rodada semanal

1. Abrir https://sellout-production-f696.up.railway.app
2. Enviar `sellout geral.xlsx` e `Sellout Clássicos.xlsx`
3. Conferir a tela de revisão — em especial **De onde vêm os números**, que
   mostra de qual coluna sai cada quantidade, com amostra do conteúdo
4. Gerar e baixar os três arquivos

Pelo terminal, sem o app:

```bash
python -m sellout.cli "sellout geral.xlsx" "Sellout Clássicos.xlsx" -s saida/
python -m sellout.cli geral.xlsx classicos.xlsx --so-analisar   # só diagnóstico
```

## O que conferir antes de usar a saída

| Sinal | O que significa |
|---|---|
| Painel vermelho na tela de revisão | O layout da origem mudou; leia antes de gerar |
| Estoque muito diferente da semana anterior | Coluna deslocada na origem, ou filial que saiu do export |
| Muitos códigos em REVISAR | O texto em vermelho pode ter se perdido na planilha de entrada |
| Aba Pendências do relatório | Linhas que não foram atualizadas e por quê |

## Voltar a uma versão anterior

O ponto de retorno do processo por planilha, conferido e funcionando, é a tag
`v1.0`.

```bash
git checkout v1.0
git push origin HEAD:main --force-with-lease
```

Ou, sem mexer no repositório: no Railway, em Deployments, abrir o deploy
desejado e usar **Redeploy**. Volta em cerca de um minuto.

## Publicar uma alteração

```bash
git push origin main
```

O Railway reconstrói sozinho. Se não disparar, o GitHub App perdeu acesso ao
repositório — em Settings → Source, reconectar `sergiofurlani/app_sellout`.

## Testes

```bash
python -m pytest
```

Cobrem o casamento de nomes de cor, a divisão pelo vermelho e a detecção de
colunas nas abas de origem — as três partes onde um erro passa despercebido.

## Variáveis

| Variável | Padrão | Para quê |
|---|---|---|
| `SELLOUT_WORKDIR` | `/tmp/sellout-jobs` | pasta de trabalho das rodadas |
| `SELLOUT_TTL_HORAS` | `6` | por quanto tempo os arquivos ficam disponíveis |
| `SELLOUT_MAX_MB` | `60` | tamanho máximo de cada upload |
