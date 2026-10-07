---
name: "Que horas voto?"
description: "Instrumento de apuração em preto quente: um mapa laranja da fila e uma frase com o melhor horário da seção."
colors:
  fundo: "#0f0e0d"
  sup: "#1b1a17"
  sup-2: "#24221f"
  fio: "rgba(250,250,249,.08)"
  fio-forte: "rgba(250,250,249,.16)"
  texto: "#fafaf9"
  apoio: "#a6a39c"
  pilula: "rgba(250,250,249,.07)"
  pilula-ativa: "rgba(250,250,249,.14)"
  tranquilo: "#0ca30c"
  movimentado: "#fab219"
  fila: "#d03b3b"
  f0: "#634533"
  f1: "#895433"
  f2: "#a95e2c"
  f3: "#d8732b"
  f4: "#f88a3d"
  f5: "#ffab69"
  sem-dado: "#2a2825"
typography:
  display:
    fontFamily: "Faustina, Georgia, serif"
    fontSize: "clamp(2rem, 7vw, 2.75rem)"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  resposta:
    fontFamily: "Faustina, Georgia, serif"
    fontSize: "clamp(2.25rem, 9vw, 3.25rem)"
    fontWeight: 400
    lineHeight: 1.05
  title:
    fontFamily: "Faustina, Georgia, serif"
    fontSize: "22px"
    fontWeight: 400
    lineHeight: 1.2
  body:
    fontFamily: 'Geist, "Helvetica Neue", Helvetica, Arial, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: 'Geist, "Helvetica Neue", Helvetica, Arial, sans-serif'
    fontSize: "13px"
    fontWeight: 500
    lineHeight: 1.5
  numero:
    fontFamily: 'Geist, "Helvetica Neue", Helvetica, Arial, sans-serif'
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.5
    fontFeature: "tnum"
rounded:
  barra: "4px"
  etiqueta: "6px"
  campo: "12px"
  card: "16px"
  pilula: "100px"
spacing:
  pequeno: "8px"
  campo: "12px"
  celular: "16px"
  card: "20px"
  bloco: "24px"
  desktop: "32px"
  colunas: "40px"
components:
  card:
    backgroundColor: "{colors.sup}"
    textColor: "{colors.texto}"
    rounded: "{rounded.card}"
    padding: "20px"
  select:
    backgroundColor: "{colors.pilula}"
    textColor: "{colors.texto}"
    rounded: "{rounded.campo}"
    height: "48px"
  voltar:
    backgroundColor: "{colors.pilula}"
    textColor: "{colors.texto}"
    rounded: "{rounded.pilula}"
    height: "36px"
  chip:
    backgroundColor: "{colors.pilula}"
    textColor: "{colors.texto}"
    rounded: "{rounded.pilula}"
    height: "28px"
  alternar:
    backgroundColor: "{colors.sup-2}"
    textColor: "{colors.apoio}"
    rounded: "{rounded.pilula}"
  alternar-ativo:
    backgroundColor: "{colors.pilula-ativa}"
    textColor: "{colors.texto}"
    rounded: "{rounded.pilula}"
    height: "36px"
  mapa-etiqueta:
    textColor: "{colors.fundo}"
    rounded: "{rounded.etiqueta}"
    height: "28px"
    width: "64px"
---

# Design System: Que horas voto?

## Overview

**Creative North Star: "Um instrumento de apuração para uma pergunta só"**

A pergunta é "a que horas eu vou?". O mapa é navegação e contexto; a resposta é uma frase em serifa ("Vá entre 13:00 e 13:30"). A linguagem visual (preto quente, cards escuros de borda fina, pílulas, sans limpa com serifa nos títulos, mapa com bordas pretas) foi fixada pelo usuário a partir do seuimposto.com. Apenas a linguagem é herdada: logo, nome, marca e textos deles não entram.

O mundo é escuro, tonal e plano. Profundidade vem de três camadas de superfície e fios de 1px; a única cor saturada da página é o laranja do mapa. A interface é feita para o celular a 375px, com o desktop como reorganização em duas colunas.

**Key Characteristics:**
- Preto quente com superfícies tonais, sem sombra em cards.
- Faustina nos títulos e na frase da resposta, Geist em todo o resto, números tabulares.
- Mapa em rampa laranja de seis degraus; verde, amarelo e vermelho só no gráfico e no chip de nível.
- Pílulas de raio 100px para controles e chips.
- Fontes hospedadas localmente.

## Colors

Preto quente, texto quase branco, apoio cinza quente e uma rampa laranja que pertence ao mapa.

### Primary
- **Laranja de fila** (`f0` a `f5`, #634533, #895433, #a95e2c, #d8732b, #f88a3d, #ffab69): rampa de seis degraus do mapa, do marrom escuro ao laranja claro. O degrau vem de `faixaFila` em `site/calc.mjs` sobre a % de fila: abaixo de 10, 10, 15, 20, 25 e 30 ou mais (limites 10/15/20/25/30). É a mesma rampa nos estados, nos municípios, nas etiquetas laterais e na legenda.

### Secondary
- **Tranquilo** (`tranquilo`, #0ca30c), **Movimentado** (`movimentado`, #fab219), **Fila** (`fila`, #d03b3b): níveis do bloco de meia hora (menos de 25%, 25 a 50%, mais de 50%). Aparecem nas barras do gráfico, na legenda e no ponto do chip de nível. `movimentado` também colore as mensagens de status e de ausência de log.

### Neutral
- **Preto quente** (`fundo`, #0f0e0d): página, e contorno dos recortes do mapa.
- **Superfície** (`sup`, #1b1a17): cards, tooltip, opções de select.
- **Superfície elevada** (`sup-2`, #24221f): trilho do controle segmentado.
- **Texto** (`texto`, #fafaf9): texto principal, foco, contorno do selecionado.
- **Apoio** (`apoio`, #a6a39c): rótulos, notas, texto secundário.
- **Fio** (`fio`, 8% de branco) e **Fio forte** (`fio-forte`, 16%): bordas de card e divisórias; borda de campo e linhas do mapa.
- **Pílula** (`pilula`, 7%) e **Pílula ativa** (`pilula-ativa`, 14%): preenchimento de chips, campos, botões e item ativo.
- **Sem dado** (`sem-dado`, #2a2825): município ou estado sem medição, com texto na legenda.

### Named Rules
**The Tinta por Degrau Rule.** Rótulos sobre o mapa usam `fundo` (escuro) nos degraus 3 a 5 e `texto` (claro) nos degraus 0 a 2, decididos por `tinta()` em `site/mapa.js`. O laranja claro não sustenta texto branco; `f2` com `texto` mede 4,65:1 e é o piso. Escurecer `f2` ou mover o corte exige recalcular.

**The Status Reservado Rule.** Verde, amarelo e vermelho significam nível do bloco e nada mais. Nunca pintam o mapa, que usa só o laranja, e nunca decoram.

**The Nunca Só Cor Rule.** Nível e ausência de dado sempre levam texto (rótulo do chip, percentual, "Sem dado") junto da cor.

## Typography

**Display Font:** Faustina (com Georgia, serif), 400, recorte latino
**Body Font:** Geist (com Helvetica Neue, Helvetica, Arial, sans-serif), pesos 400 a 600, recorte latino

**Character:** Serifa editorial para o que se lê como frase, sans técnica para o que se lê como instrumento. Ambas autohospedadas em `site/fonts` (WOFF2, `font-display: swap`, licença OFL junto), Geist com preload.

### Hierarchy
- **Display** (400, clamp(2rem, 7vw, 2.75rem), 1.1, -0.02em): o nome da ferramenta, uma vez.
- **Resposta** (400, clamp(2.25rem, 9vw, 3.25rem), 1.05): a frase "Vá entre ...", com o horário em Geist 600, tabular, -0.03em, sem quebra.
- **Title** (400, 22px, 1.2; 20px no painel do mapa): títulos de card.
- **Body** (400, 16px, 1.5): texto corrido, selects.
- **Label** (500, 13px): rótulos de campo, notas, contexto, legendas; 11 a 12px só em dado denso (tabela, ranking, etiquetas do mapa).
- **Número** (600, 18px, tabular): métricas da resposta; o ranking usa 16px.

### Named Rules
**The Número Tabular Rule.** Todo número (horário, percentual, contagem, eixo) usa `font-variant-numeric: tabular-nums`.

**The Serifa Só Em Título Rule.** Faustina aparece em `h1` e `h2`. Nada de controle, rótulo ou dado em serifa.

## Layout

Coluna única até 1023px: cabeçalho, mapa, consulta (seletor, resposta, gráfico, ranking), rodapé. Largura máxima de 1240px, margem lateral de 16px, intervalo de 24px entre blocos. A 375px o mapa do Brasil ocupa a largura toda e cabe no primeiro viewport, com as etiquetas dos estados pequenos à direita (76px reservados, etiquetas de 64px).

A partir de 1024px: duas colunas `minmax(0, 1.15fr) minmax(0, 1fr)`, intervalo de 40px, margem de 32px; mapa à esquerda e sticky a 24px do topo, consulta à direita; cabeçalho e rodapé nas duas colunas. Selects em grade 2x2. Escala de espaço usada: 8, 12, 16, 20, 24, 32, 40px.

## Elevation & Depth

Plano e tonal. Cards não têm sombra: a separação vem de `fundo`, `sup` e `sup-2` mais fio de 1px. A única sombra é a do tooltip flutuante do mapa, suave e difusa, mostrada só com hover real.

### Shadow Vocabulary
- **Tooltip** (`box-shadow: 0 8px 24px rgba(0,0,0,.45)`): card flutuante do mapa.

### Named Rules
**The Plano Por Padrão Rule.** Superfície em repouso não tem sombra; só o que flutua sobre o mapa tem.

## Shapes

Cantos generosos e consistentes: cards 16px, campos e tooltip 12px, etiquetas laterais 6px, barras do gráfico 4px nos cantos superiores, e 100px (pílula) para chips, botão de voltar e controle segmentado. Seleção no mapa por contorno `texto` de 2px, desenhado por último. Ícones são SVG inline de traço 1,5px.

## Components

### Card
`sup`, fio de 1px, raio 16px, padding 20px (24 a 28px na resposta, que usa `fio-forte`).

### Select
Nativo, 48px, fundo `pilula`, borda `fio-forte`, raio 12px, seta SVG, rótulo de 13px sempre visível. Hover leva a borda a `apoio`; desligado usa texto `apoio` e fundo mais apagado.

### Chip de nível e Voltar
Pílula de `pilula`; o chip tem 28px e leva ponto de 8px na cor do nível mais o texto; o botão Voltar tem 36px, seta SVG e hover `pilula-ativa`.

### Controle segmentado
Trilho `sup-2` em pílula; item ativo (`aria-pressed`) em `pilula-ativa` e `texto`. Rótulo visível "Cinza atrás:" acima.

### Mapa
SVG com recortes do IBGE, bordas `fundo`, preenchimento pela rampa `f0` a `f5` ou `sem-dado`. Rótulos de percentual dentro dos estados, etiquetas laterais para os pequenos ligadas por linha `fio-forte`, legenda com os seis degraus e o "Sem dado". Entrada no estado em 420ms, opacidade e escala de .97 a 1, `cubic-bezier(.16,1,.3,1)`, desligada com `prefers-reduced-motion`.

### Gráfico e ranking
Barras de 200px de altura nos três status, 2024 como fantasma cinza atrás, melhor bloco com contorno `texto`, tabela expansível com os mesmos números. Ranking em linhas separadas por fio, posição e percentual tabulares, a seção do usuário em `pilula` com o texto "sua seção".

Foco: outline de 2px em `texto`, afastado 2px, em tudo.

## Do's and Don'ts

### Do:
- **Do** manter Faustina só em títulos e na frase, Geist no resto, números tabulares.
- **Do** escolher a cor da tinta do rótulo do mapa pelo degrau (escuro no 3 ao 5, claro no 0 ao 2).
- **Do** reservar verde, amarelo e vermelho aos níveis do gráfico e do chip.
- **Do** manter selects nativos, foco visível e a tabela do gráfico como caminho completo sem o mapa.

### Don't:
- **Don't** usar logo, nome, marca ou textos do seuimposto.com; só a linguagem visual.
- **Don't** pintar o mapa com a paleta de status nem usar o laranja fora do mapa e da sua legenda.
- **Don't** empilhar cards iguais nem repetir o template de número gigante com estatísticas.
- **Don't** usar gradiente, glow, glass, emoji ou glifo como ícone.
- **Don't** substituir Faustina ou Geist por fonte de sistema nem carregar fonte de CDN.

## Não canonizado

- A linha de status ("1º turno de 2026 · 5.571 cidades ...") com ponto, sob o título, é conteúdo da página, não padrão para novas superfícies.
- Texto de 11 a 12px em etiquetas, tabela e ranking fica abaixo do piso de 13px do sistema; é concessão de densidade do build, não escala a herdar.
