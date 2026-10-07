# Redesign com mapa do Brasil

## Intenção
- O site deixa de parecer gerado: adota a linguagem visual de seuimposto.com (preto quente, Geist + Faustina, pílulas, cards de borda fina, mapa cinza com bordas pretas), sem logo, nome nem textos deles.
- Um mapa do Brasil no topo pinta cada estado pela % de eleitores que pegaram fila no 1º turno de 2026; tocar no estado entra nele e mostra os municípios pintados do mesmo jeito; tocar no município seleciona (o mesmo que o select). Passar o mouse mostra um card com nome e %.
- Os selects continuam como caminho completo (celular, teclado, leitor de tela). O resultado da seção (melhor horário, números, gráfico, ranking) mantém o conteúdo e ganha a linguagem nova.

## Critério de aceite
1. `python3.12 -m unittest discover -s pipeline` termina em `OK` (inclui os testes de `pipeline/mapa.py`).
2. `python3.12 pipeline/mapa.py --saida site/data` imprime `27 UFs, 5571 municípios, 0 sem contorno` e grava `site/data/mapa/br.json` (Boa Esperança do Norte/MT, criado em 2023, não tem malha no IBGE: fica fora do mapa e nos selects) e `site/data/mapa/<uf>.json`.
3. `du -ch site/data/mapa/*.json | tail -1` fica abaixo de `3,0M`, e nenhum arquivo passa de 600 KB.
4. `node --test test/` passa (inclui `faixaFila` em `calc.mjs`).
5. Capturas a 375 px e 1280 px de `#`, `#mg` e `#pb/19313/0014/0001` mostram o mapa pintado com legenda, o estado aberto com municípios e o município selecionado contornado; `detect.mjs` sem achado mecânico aberto.
6. `npx wrangler deploy` e `curl -s -o /dev/null -w "%{http_code}" <url>/data/mapa/br.json` imprime `200`.

## Fora de escopo
- Mudar a coleta do TSE, o esquema dos JSON por município, o formato do hash ou a regra de fila.
- Mapa por zona ou por seção (não há contorno oficial de zona eleitoral).
- Dados do 2º turno de 2026.
