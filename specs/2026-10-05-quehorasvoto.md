# quehorasvoto

## Intenção

O eleitor escolhe UF > município > zona > seção e vê, em blocos de meia hora (hora local), quantas pessoas votaram na sua seção no 1º turno de 2026 e na eleição municipal de 2024, com o melhor horário destacado e o nível de fila de cada bloco (tranquilo / movimentado / fila). Também vê o ranking das seções do município com mais fila. O objetivo é escolher o horário menos cheio para o 2º turno de 25/10/2026. Site estático, dark, com a usabilidade do seuimposto.com e identidade própria, no ar até 18/10/2026.

## Decisões

| # | Decisão | Motivo |
|---|---|---|
| D1 | Eleições: 2026 1º turno (pleito `3220`, ciclo `ele2026`), 2024 1º e 2º turno (pleitos `452`/`453`, ciclo `ele2024`) | São as únicas com log por seção na API `resultados.tse.jus.br`; 2022 só existe em pacote por UF de 1,4–1,9 GB; 2018/2020 não têm log publicado |
| D2 | Pré-cálculo total por GitHub Action, um job por UF, rodado uma vez; saída é um JSON estático por município | O ranking precisa de todas as seções; Worker Free só faz 50 subrequests; no dia 25/10 o site não depende do TSE |
| D3 | Pipeline em Python só com stdlib (`urllib`, `zipfile`, `json`) | `.jez` é zip e `logd.dat` é latin1; nada pede dependência |
| D4 | Frontend Preact + `htm` sem build, servido como assets estáticos por um Cloudflare Worker em `*.workers.dev` | Mesma base do seuimposto; Next traria build e SSR sem uso |
| D5 | Granularidade de meia hora, hora local (como o log já registra; no Acre a votação aparece 06h–15h) | O pico de 8h–8h30 some na hora cheia |
| D6 | Fila: por bloco, fração de eleitores habilitados menos de 30 s depois do voto anterior computado. `<25%` tranquilo, `25–50%` movimentado, `>50%` fila. Limites calibrados em ~20 seções reais antes do lançamento | Gap curto entre fim de voto e próxima habilitação indica gente esperando; na seção 0001/z14 de Bananeiras-PB, 104 de 270 gaps ficaram abaixo de 30 s |
| D7 | Gráfico: 2026 em destaque, 2024 sobreposto e apagado; sem média entre eleições | O TSE renumera e funde seções; média esconderia isso |
| D8 | Ranking no município, filtro opcional por zona, ordenado por % de eleitores que pegaram fila | Total de eleitores premia seção grande, não seção com fila |
| D9 | Achar a seção: 4 selects, link para o "Onde votar" do TSE, URL `#uf/municipio/zona/secao` compartilhável, última seção lembrada no aparelho | Muita gente não sabe a seção de cabeça; o link é o que circula no WhatsApp |
| D10 | Repo público `dv-dev1/quehorasvoto`, MIT | Projeto aberto ao público |

## Fontes (verificadas em 05/10/2026)

- Seções: `https://resultados.tse.jus.br/oficial/<ciclo>/arquivo-urna/<pleito>/config/<uf>/<uf>-p<pleito:06d>-cs.json` → `abr[0].mu[].{cd,nm,zon[].{cd,sec[].ns}}`
- Arquivos da seção: `.../arquivo-urna/<pleito>/dados/<uf>/<mun>/<zona>/<secao>/p<pleito:06d>-<uf>-m<mun>-z<zona>-s<secao>-aux.json` → `hashes[].{hash,arq[].{nm,tp}}`, log é `tp == "log"`
- Log: `.../<secao>/<hash>/<nm>` → zip com `logd.dat`, latin1, TSV `data hora \t nível \t id \t módulo \t mensagem \t mac`
- Eventos: `Eleitor foi habilitado` e `O voto do eleitor foi computado`, só linhas com a data do pleito
- Sem cabeçalho CORS: o navegador não consegue buscar direto do TSE

## Critério de aceite

1. Parser de uma seção:
   ```
   python3 pipeline/quehorasvoto.py secao --pleito 3220 pb 19313 0014 0001
   ```
   imprime um JSON com blocos de meia hora de `08:00` a `16:30`, e a soma de `eleitores` é `271`.
2. Testes do pipeline passam e falham quando a regra de fila é quebrada:
   ```
   python3 -m unittest discover -s pipeline
   ```
   saída termina em `OK`.
3. Município inteiro:
   ```
   python3 pipeline/quehorasvoto.py municipio pb 19313 --saida site/data
   ```
   gera `site/data/pb/19313.json` com todas as seções de 2026 e 2024 e o campo `ranking` ordenado por `% fila` decrescente.
4. Site local:
   ```
   npx wrangler dev & sleep 5; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/ http://localhost:8787/data/pb/19313.json
   ```
   imprime `200` duas vezes.
5. `.github/workflows/dados.yml` tem uma matriz com as 27 UFs e roda manualmente (`workflow_dispatch`); `.github/workflows/ci.yml` roda `ruff check` e os testes em duas versões de Python.
6. Deploy: `npx wrangler deploy` imprime a URL `https://quehorasvoto.<conta>.workers.dev`, e abrir `#pb/19313/0014/0001` nela mostra o gráfico, o melhor horário e o ranking de Bananeiras.

## Fora de escopo

- Tempo real: o log só sai depois que a urna fecha.
- Mapa, visão por local de votação e média entre eleições.
- Eleições de 2018, 2020 e 2022.
- Domínio próprio: fica no `workers.dev` até ganhar tração.
- Busca da seção pelo título de eleitor: só o link para o TSE.
