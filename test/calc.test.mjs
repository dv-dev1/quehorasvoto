import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  pct, nivel, horaDoBloco, faixa, serie, linhaDoTempo, melhorBloco, lerHash, montarHash, posicaoNoRanking,
} from '../site/calc.mjs';

test('nivel nas bordas', () => {
  assert.equal(nivel(24), 'tranquilo');
  assert.equal(nivel(25), 'movimentado');
  assert.equal(nivel(50), 'movimentado');
  assert.equal(nivel(51), 'fila');
});

test('pct', () => {
  assert.equal(pct(1, 3), 33);
  assert.equal(pct(0, 0), 0);
});

test('horas', () => {
  assert.equal(horaDoBloco('08:00', 3), '09:30');
  assert.equal(horaDoBloco('06:30', 1), '07:00');
  assert.equal(faixa('13:00'), '13:00–13:30');
});

test('serie', () => {
  assert.deepEqual(serie(null), []);
  assert.deepEqual(serie({ inicio: '08:00', eleitores: [4, 0], fila: [2, 0] }), [
    { hora: '08:00', eleitores: 4, fila: 2, pct: 50, nivel: 'movimentado' },
    { hora: '08:30', eleitores: 0, fila: 0, pct: 0, nivel: 'tranquilo' },
  ]);
});

test('linhaDoTempo junta series com inícios diferentes', () => {
  const a = serie({ inicio: '08:00', eleitores: [1, 1, 1], fila: [0, 0, 0] });
  const b = serie({ inicio: '07:30', eleitores: [1, 1], fila: [0, 0] });
  assert.deepEqual(linhaDoTempo(a, b), ['07:30', '08:00', '08:30', '09:00']);
});

test('melhorBloco ignora bloco vazio e desempata por menos eleitores e mais cedo', () => {
  const s = serie({ inicio: '08:00', eleitores: [10, 0, 10, 5, 5, 8], fila: [5, 0, 0, 0, 0, 0] });
  assert.equal(melhorBloco(s).hora, '09:30');
  assert.equal(melhorBloco([]), null);
});

test('melhorBloco ignora quem votou na fila depois do fechamento', () => {
  const eleitores = [...Array(18).fill(10), 2];
  const s = serie({ inicio: '08:00', eleitores, fila: [...Array(17).fill(3), 0, 0] });
  assert.equal(melhorBloco(s).hora, '16:30');
  const acre = serie({ inicio: '06:00', eleitores, fila: [...Array(17).fill(3), 0, 0] });
  assert.equal(melhorBloco(acre).hora, '14:30');
});

test('lerHash aceita só o formato esperado', () => {
  assert.deepEqual(lerHash('#pb/19313/0014/0001'), { uf: 'pb', mun: '19313', zona: '0014', secao: '0001' });
  assert.deepEqual(lerHash('#PB/19313'), { uf: 'pb', mun: '19313' });
  assert.deepEqual(lerHash('#pb/abc/0014'), { uf: 'pb' });
  assert.deepEqual(lerHash('#../../etc'), {});
  assert.deepEqual(lerHash(''), {});
});

test('montarHash', () => {
  assert.equal(montarHash({ uf: 'pb', mun: '19313' }), '#pb/19313');
  assert.equal(montarHash({}), '');
});

test('posicaoNoRanking com e sem zona', () => {
  const r = [['0014/0002', 80, 10], ['0015/0001', 60, 9], ['0014/0001', 40, 8]];
  assert.deepEqual(posicaoNoRanking(r, '0014/0001'), { pos: 3, total: 3 });
  assert.deepEqual(posicaoNoRanking(r, '0014/0001', '0014'), { pos: 2, total: 2 });
  assert.equal(posicaoNoRanking(r, '0099/0001'), null);
});
