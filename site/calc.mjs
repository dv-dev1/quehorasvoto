export const LIMITES = { movimentado: 25, fila: 50 };

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

export function melhorBloco(s) {
  const com = s.filter((b) => b.eleitores > 0);
  if (!com.length) return null;
  return com.reduce((a, b) => (b.pct < a.pct || (b.pct === a.pct && b.eleitores < a.eleitores) ? b : a));
}

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
