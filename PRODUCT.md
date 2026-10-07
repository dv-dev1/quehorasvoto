# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Eleitor brasileiro, quase sempre no celular, nos dias antes do 2º turno de 25/10/2026. Sabe (ou consulta no TSE) a zona e a seção onde vota e quer saber a que horas ir para pegar menos fila. Visita curta: acha a seção, lê o melhor horário, vai embora.

## Product Purpose

Mostrar, para cada seção eleitoral do país, quantas pessoas votaram em cada meia hora no 1º turno de 2026 e quantas pegaram fila, e apontar o bloco de 30 min mais tranquilo. Sucesso: o eleitor lê o melhor horário da própria seção em poucos segundos e confia no número.

## Positioning

Única fonte que usa o log de cada urna do TSE (o registro de cada eleitor habilitado, segundo a segundo) para medir fila de verdade por seção, em todas as 5.571 cidades, e não estimativa por bairro ou por relato.

## Operating Context

- Navegação Estado > município > zona > seção, com link para a consulta oficial do TSE para quem não sabe a seção.
- Mapa do Brasil como atalho e contexto: estados pintados pela % de fila, ao entrar no estado os municípios pintados do mesmo jeito; tocar no município seleciona. Os selects continuam ao lado do mapa (celular e acessibilidade).
- Comparação com 2024 (1º e 2º turnos municipais) como fundo do gráfico.
- Uso no celular a 375 px é o caso principal; desktop é secundário.

## Capabilities and Constraints

- Site estático, Preact + htm sem build, servido por Cloudflare Worker (workers.dev). Dados pré-calculados em JSON por município (`site/data/<uf>/<mun>.json`), coletados por GitHub Action.
- Fila = eleitor habilitado menos de 30 s depois do voto anterior. Níveis por bloco: tranquilo < 25%, movimentado 25–50%, fila > 50%.
- Hora local da urna (Acre abre às 06h, fusos de 07h no Norte/Centro-Oeste).
- Contornos do mapa vêm da malha oficial do IBGE; o código de município do TSE é ligado ao do IBGE pelo nome (13 grafias diferentes tratadas à mão).
- Não há dados do 2º turno de 2026 antes da eleição; o site não prevê, mostra o que aconteceu.

## Brand Commitments

- Nome: "Que horas voto?" (repo `quehorasvoto`), código aberto MIT.
- Referência de linguagem visual escolhida pelo usuário: seuimposto.com (apuração 2026) — mesma linguagem (fundo preto quente, sans limpa com serifa no título, pílulas, cards escuros de borda fina, mapa cinza com bordas pretas e card flutuante). Não usar logo, nome, marca nem textos deles.

## Evidence on Hand

- Dados reais: logs do TSE de ~498 mil seções (1º turno 2026) e 2024, em `site/data/`.
- Sem depoimentos, imprensa ou números de uso: não inventar.

## Product Principles

1. O melhor horário da seção é a resposta; tudo o mais é contexto.
2. Nível de fila nunca só por cor: texto e número junto.
3. Dado do TSE como está, com a regra explicada em uma linha; sem previsão.
4. Funciona no celular com uma mão, em 4G fraco.

## Accessibility & Inclusion

Contraste AA, foco visível, tabela com os mesmos números do gráfico, selects nativos como caminho completo sem o mapa.
