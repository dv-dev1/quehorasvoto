# quehorasvoto

Mostra quantas pessoas votaram em cada meia hora na sua seção eleitoral, a partir dos logs de urna publicados pelo TSE.
Serve para escolher o horário mais vazio no 2º turno de 25/10/2026.

```
$ python3 pipeline/quehorasvoto.py secao --pleito 3220 pb 19313 0014 0001
{"inicio": "08:00", "eleitores": [17, 9, 15, 15, 15, 18, 21, 11, 16, 17, 13, 12, 22, 18, 15, 12, 14, 11], "fila": [3, 3, 4, 8, 5, 10, 9, 1, 10, 5, 0, 3, 17, 10, 5, 4, 5, 2]}
```

`eleitores` é quantas pessoas foram habilitadas na urna em cada bloco de 30 min a partir de `inicio`; `fila` é quantas delas foram habilitadas menos de 30 s depois do voto anterior, sinal de que já havia gente esperando.

## Como funciona

1. `pipeline/quehorasvoto.py` baixa o `aux.json` e o log (`.jez`) de cada seção em `resultados.tse.jus.br` e conta os eventos `Eleitor foi habilitado` e `O voto do eleitor foi computado`.
2. A Action `dados` roda isso para as 27 UFs e grava um JSON por município em `site/data/`.
3. `site/` é uma página estática (Preact + htm, sem build) servida por um Cloudflare Worker.

Eleições cobertas: 1º turno de 2026 e 1º e 2º turnos de 2024, as únicas com log por seção na API do TSE.

## Rodar localmente

```bash
python3 -m unittest discover -s pipeline
node --test test/calc.test.mjs
python3 pipeline/quehorasvoto.py municipio pb 19313 --saida site/data
npx wrangler dev
```

O pipeline usa só a biblioteca padrão do Python 3.11+ (o CI quebra se isso deixar de ser verdade).

## Licença

MIT
