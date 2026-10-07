export const LIMITES = { movimentado: 25, fila: 50 };

export const FAIXAS_FILA = [10, 15, 20, 25, 30];

export function faixaFila(p) {
  if (p == null) return null;
  const i = FAIXAS_FILA.findIndex((limite) => p < limite);
  return i < 0 ? FAIXAS_FILA.length : i;
}

export const pct = (fila, eleitores) => (eleitores ? Math.round((100 * fila) / eleitores) : 0);

export function nivel(p) {
  if (p < LIMITES.movimentado) return 'tranquilo';
  if (p <= LIMITES.fila) return 'movimentado';
  return 'fila';
}

const dois = (n) => String(n).padStart(2, '0');

export function horaDoBloco(inicio, i) {
  const [h, m] = inicio.split(':').map(Number);
  const t = h * 60 + m + 30 * i;
  return `${dois(Math.floor(t / 60))}:${dois(t % 60)}`;
}

export const faixa = (hora) => `${hora}–${horaDoBloco(hora, 1)}`;

export function serie(d) {
  if (!d) return [];
  return d.eleitores.map((n, i) => {
    const p = pct(d.fila[i], n);
    return { hora: horaDoBloco(d.inicio, i), eleitores: n, fila: d.fila[i], pct: p, nivel: nivel(p) };
  });
}

export const linhaDoTempo = (...series) => [...new Set(series.flat().map((b) => b.hora))].sort();

// A urna abre na hora cheia e fica 9 h aberta; depois disso só vota quem já estava na fila, e esse bloco
// vazio venceria o desempate por menos eleitores.
const BLOCOS_DE_VOTACAO = 18;

export function melhorBloco(s, abertura = s[0]?.hora) {
  if (!s.length) return null;
  const fim = horaDoBloco(`${abertura.slice(0, 2)}:00`, BLOCOS_DE_VOTACAO);
  const com = s.filter((b) => b.eleitores > 0 && b.hora < fim);
  if (!com.length) return null;
  return com.reduce((a, b) => (b.pct < a.pct || (b.pct === a.pct && b.eleitores < a.eleitores) ? b : a));
}

export function aberturaDoMunicipio(secoes) {
  const contagem = {};
  for (const secao of Object.values(secoes)) {
    const inicio = secao['3220']?.inicio;
    if (inicio) contagem[inicio] = (contagem[inicio] || 0) + 1;
  }
  return Object.keys(contagem).sort((a, b) => contagem[b] - contagem[a] || a.localeCompare(b))[0];
}

const MINUSCULAS = new Set(['de', 'da', 'do', 'das', 'dos', 'e']);
export const nome = (s) => s.toLowerCase().replace(/[^\s'-]+/g, (w, i) => (i && MINUSCULAS.has(w) ? w : w[0].toUpperCase() + w.slice(1)));

// O hash vira caminho de fetch: validar cada parte impede buscar qualquer coisa fora de data/<uf>/<mun>.json.
const PARTES = [['uf', /^[a-z]{2}$/], ['mun', /^\d{5}$/], ['zona', /^\d{4}$/], ['secao', /^\d{4}$/]];

export function lerHash(hash) {
  const partes = hash.replace(/^#/, '').toLowerCase().split('/');
  const sel = {};
  for (const [i, [nome, re]] of PARTES.entries()) {
    if (!re.test(partes[i] ?? '')) break;
    sel[nome] = partes[i];
  }
  return sel;
}

export function montarHash(sel) {
  const v = [];
  for (const [nome] of PARTES) {
    if (!sel[nome]) break;
    v.push(sel[nome]);
  }
  return v.length ? `#${v.join('/')}` : '';
}

export function posicaoNoRanking(ranking, chave, zona) {
  const lista = zona ? ranking.filter(([k]) => k.startsWith(`${zona}/`)) : ranking;
  const i = lista.findIndex(([k]) => k === chave);
  return i < 0 ? null : { pos: i + 1, total: lista.length };
}
