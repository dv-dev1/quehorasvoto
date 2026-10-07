import { html, render, useState, useEffect, useRef } from './vendor/preact-htm.mjs';
import { serie, melhorBloco, aberturaDoMunicipio, linhaDoTempo, lerHash, montarHash, posicaoNoRanking, faixa, horaDoBloco, pct, nome } from './calc.mjs';
import { Mapa, UFS } from './mapa.js';
const ONDE_VOTAR = 'https://www.tse.jus.br/servicos-eleitorais/autoatendimento-eleitoral#/';
const votaram = (n) => `${n} ${n === 1 ? 'votou' : 'votaram'}`;
const ROTULO = { tranquilo: 'Tranquilo', movimentado: 'Movimentado', fila: 'Fila' };
const TURNO24 = { 452: '2024 · 1º turno', 453: '2024 · 2º turno' };
const CHAVE = 'qhv:ultima';

// O clique no ranking troca o hash e o card novo monta mais acima da página: o foco tem que ir junto.
let focarMelhor = false;

const lembrar = (h) => { try { localStorage.setItem(CHAVE, h); } catch { /* aba anônima */ } };
const lembrada = () => { try { return localStorage.getItem(CHAVE) || ''; } catch { return ''; } };

async function buscar(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function mostrarResposta(elemento, focar = false) {
  if (!elemento) return;
  if (focar) elemento.focus({ preventScroll: true });
  elemento.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}

function Select({ rotulo, valor, opcoes, aoMudar, desligado, vazio = 'Escolha' }) {
  return html`<label class="campo"><span>${rotulo}</span>
    <select value=${valor || ''} disabled=${desligado} onChange=${(e) => aoMudar(e.target.value || undefined)}>
      <option value="">${vazio}</option>
      ${opcoes.map(([v, t]) => html`<option value=${v}>${t}</option>`)}
    </select></label>`;
}

function Grafico({ s26, s24, rotulo24, melhor }) {
  const horas = linhaDoTempo(s26, s24);
  const max = Math.max(1, ...s26.map((b) => b.eleitores), ...s24.map((b) => b.eleitores));
  const por = (s) => Object.fromEntries(s.map((b) => [b.hora, b]));
  const a = por(s26), b = por(s24);
  const alt = (x) => `${(100 * x.eleitores) / max}%`;
  const [foco, setFoco] = useState(melhor.hora);
  const x = a[foco], y = b[foco];
  return html`
    <p class="leitura" aria-hidden="true"><strong>${faixa(foco)}</strong>
      <span>2026: ${x ? `${votaram(x.eleitores)}, ${x.pct}% pegaram fila` : 'ninguém votou'}</span>
      ${s24.length ? html`<span>${rotulo24}: ${votaram(y ? y.eleitores : 0)}</span>` : ''}</p>
    <div class="grafico" role="img" aria-label=${`Eleitores por meia hora no 1º turno de 2026, com ${rotulo24 || '2024'} atrás. Melhor horário: ${faixa(melhor.hora)}.`}>
      ${horas.map((h) => html`
        <div class=${`coluna ${melhor.hora === h ? 'melhor' : ''} ${foco === h ? 'ativa' : ''}`}
          onPointerEnter=${() => setFoco(h)} onClick=${() => setFoco(h)}>
          <div class="barras">
            ${b[h] && html`<div class="fantasma" style=${{ height: alt(b[h]) }}></div>`}
            ${a[h] && html`<div class=${`barra ${a[h].nivel}`} style=${{ height: alt(a[h]) }}></div>`}
          </div>
          <span class="hora">${h.endsWith(':00') ? `${h.slice(0, 2)}h` : ''}</span>
        </div>`)}
    </div>
    <p class="legenda"><strong>1º turno 2026:</strong><span><i class="ponto tranquilo"></i>Tranquilo</span><span><i class="ponto movimentado"></i>Movimentado</span>
      <span><i class="ponto fila"></i>Fila</span>${s24.length ? html`<span><i class="ponto fantasma"></i>Cinza: ${rotulo24}</span>` : ''}</p>
    <p class="nota-grafico">Altura: quantos votaram. Cor: quantos desses pegaram fila. Passe o dedo ou o mouse nas barras.</p>
    <details><summary>Ver tabela</summary>
      <table><thead><tr><th>Horário</th><th>Votaram em 2026</th><th>Pegaram fila</th><th>Nível</th></tr></thead>
        <tbody>${s26.map((x) => html`<tr><td>${faixa(x.hora)}</td><td>${x.eleitores}</td><td>${x.pct}%</td><td>${ROTULO[x.nivel]}</td></tr>`)}</tbody>
      </table></details>`;
}

function Secao({ mun, chave }) {
  const d = mun.secoes[chave];
  const turnos = ['453', '452'].filter((p) => d[p]);
  const [p24, setP24] = useState(turnos[0]);
  const ref = useRef(null);
  useEffect(() => {
    mostrarResposta(ref.current, focarMelhor);
    focarMelhor = false;
  }, []);
  const s26 = serie(d['3220']);
  const melhor = melhorBloco(s26, aberturaDoMunicipio(mun.secoes));
  if (!melhor) {
    return html`<section id="resposta" class="card resposta vazio" tabindex="-1" ref=${ref}>Esta seção não tem log de urna em 2026 (urna substituída sem arquivo ou votação em cédula). Veja o ranking do município abaixo.</section>`;
  }
  const s24 = serie(d[p24]);
  const total = s26.reduce((t, b) => t + b.eleitores, 0);
  const pico = s26.reduce((a, b) => (b.eleitores > a.eleitores ? b : a));
  const pos = posicaoNoRanking(mun.ranking, chave);
  return html`
    <section id="resposta" class="card resposta" tabindex="-1" ref=${ref}>
      <h2 class="frase">Vá entre <span class="hora">${melhor.hora} e ${horaDoBloco(melhor.hora, 1)}</span></h2>
      <span class="chip"><i class=${`ponto ${melhor.nivel}`} aria-hidden="true"></i>${ROTULO[melhor.nivel]}</span>
      <p class="contexto">Zona ${chave.split('/')[0]} · Seção ${chave.split('/')[1]} · ${nome(mun.nm)}, ${mun.uf.toUpperCase()}</p>
      <p class="explicacao">No 1º turno de 2026, ${melhor.eleitores} ${melhor.eleitores === 1 ? 'pessoa votou' : 'pessoas votaram'} nesse bloco e ${melhor.pct}% pegaram fila.</p>
      <dl class="numeros">
        <div><dt>Votaram em 2026</dt><dd>${total}</dd></div>
        <div><dt>Pegaram fila</dt><dd>${pct(s26.reduce((t, b) => t + b.fila, 0), total)}%</dd></div>
        <div><dt>Mais cheio</dt><dd>${faixa(pico.hora)}</dd></div>
        ${pos && html`<div><dt>Fila no município</dt><dd>${pos.pos}ª de ${pos.total}</dd></div>`}
      </dl>
    </section>
    <section class="card grafico-card">
      <div class="titulo"><h2>Eleitores por meia hora no 1º turno de 2026</h2>
        ${turnos.length > 1 && html`<div class="comparacao"><span id="comparar">Cinza atrás:</span>
          <div class="alternar" role="group" aria-labelledby="comparar">${turnos.map((p) => html`
            <button aria-pressed=${p === p24} onClick=${() => setP24(p)}>${TURNO24[p]}</button>`)}</div>
        </div>`}
      </div>
      <${Grafico} s26=${s26} s24=${s24} rotulo24=${TURNO24[p24]} melhor=${melhor} />
    </section>`;
}

function Ranking({ mun, zonas, chave }) {
  const [zona, setZona] = useState('');
  const nm = nome(mun.nm);
  const lista = mun.ranking.filter(([k]) => !zona || k.startsWith(`${zona}/`)).slice(0, 10);
  return html`<section class="card ranking-card">
    <div class="titulo"><h2>Seções com mais fila em ${nm}</h2>
      ${zonas.length > 1 && html`<${Select} rotulo="Zona" valor=${zona} vazio="Todas" opcoes=${zonas.map((z) => [z, z])} aoMudar=${(z) => setZona(z || '')} />`}
    </div>
    <ol class="ranking" role="list">${lista.map(([k, p, n], i) => html`
      <li class=${k === chave ? 'sua' : ''}>
        <span class="posicao" aria-hidden="true">${i + 1}</span>
        <div class="ranking-secao"><a href=${`#${mun.uf}/${mun.cd}/${k}`} onClick=${() => {
          focarMelhor = k !== chave;
          if (k === chave) mostrarResposta(document.getElementById('resposta'), true);
        }}>Zona ${k.split('/')[0]} · Seção ${k.split('/')[1]}</a>
          ${k === chave && html`<span class="sua-secao">sua seção</span>`}
        </div>
        <div class="ranking-dados"><strong>${p}%</strong><span>${n} eleitores</span></div>
      </li>`)}</ol>
    <p class="nota">Percentual de eleitores habilitados menos de 30 s depois do voto anterior, 1º turno de 2026.</p>
  </section>`;
}

function App() {
  const [sel, setSel] = useState(() => lerHash(location.hash || lembrada()));
  const [indice, setIndice] = useState(null);
  const [mun, setMun] = useState(null);
  const [erro, setErro] = useState('');
  const seletorRef = useRef(null);

  useEffect(() => {
    const ao = () => setSel(lerHash(location.hash));
    addEventListener('hashchange', ao);
    return () => removeEventListener('hashchange', ao);
  }, []);
  useEffect(() => {
    const h = montarHash(sel);
    if (location.hash !== h) history.replaceState(null, '', h || location.pathname);
    if (sel.secao) lembrar(h);
  }, [sel]);
  useEffect(() => {
    let vivo = true;
    setIndice(null); setErro('');
    if (sel.uf) buscar(`data/${sel.uf}/index.json`).then(
      (d) => { if (vivo) setIndice(d); },
      () => { if (vivo) setErro('Os dados deste estado ainda não foram publicados.'); },
    );
    return () => { vivo = false; };
  }, [sel.uf]);
  useEffect(() => {
    let vivo = true;
    setMun(null); setErro('');
    if (sel.uf && sel.mun) buscar(`data/${sel.uf}/${sel.mun}.json`).then(
      (d) => { if (vivo) setMun(d); },
      () => { if (vivo) setErro('Os dados deste município ainda não foram publicados.'); },
    );
    return () => { vivo = false; };
  }, [sel.uf, sel.mun]);

  const municipio = mun?.uf === sel.uf && mun?.cd === sel.mun ? mun : null;
  const chaves = municipio ? Object.keys(municipio.secoes).filter((k) => '3220' in municipio.secoes[k]) : [];
  const zonas = [...new Set(chaves.map((k) => k.split('/')[0]))];
  const secoes = chaves.filter((k) => k.startsWith(`${sel.zona}/`)).map((k) => k.split('/')[1]);
  const chave = sel.zona && sel.secao ? `${sel.zona}/${sel.secao}` : null;
  const carregaUf = sel.uf && !indice && !erro;
  const carregaMun = sel.mun && !municipio && !erro;
  const status = erro || (carregaUf || carregaMun ? 'Carregando dados…' : '')
    || (municipio && chave && !municipio.secoes[chave] ? 'Seção não encontrada neste município. Confira o número no TSE.' : '');
  const semMun = !sel.mun ? 'Escolha' : erro ? 'Sem dados' : 'Carregando…';
  const aoUf = (uf) => setSel(uf ? { uf } : {});
  const aoMun = (mun) => setSel({ uf: sel.uf, mun });

  return html`
    <header><h1>Que horas voto?</h1>
      <p class="pleito"><i class="ponto apoio" aria-hidden="true"></i>1º turno de 2026 · 5.571 cidades · 2º turno em 25/10</p>
      <p>Quantas pessoas votaram em cada meia hora na sua seção. Escolha o horário mais vazio para o 2º turno, em 25/10.</p></header>
    <div class="lado-mapa"><${Mapa} sel=${sel} indice=${indice} aoUf=${aoUf} aoMun=${(mun) => {
      aoMun(mun);
      requestAnimationFrame(() => seletorRef.current?.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }));
    }} /></div>
    <div class="consulta">
    <section class="card seletor" ref=${seletorRef}>
      <${Select} rotulo="Estado" valor=${sel.uf} opcoes=${UFS} aoMudar=${aoUf} />
      <${Select} rotulo="Município" valor=${sel.mun} opcoes=${(indice || []).map(([v, t]) => [v, nome(t)])} desligado=${!indice}
        vazio=${indice || !sel.uf ? 'Escolha' : erro ? 'Sem dados' : 'Carregando…'} aoMudar=${aoMun} />
      <${Select} rotulo="Zona" valor=${sel.zona} opcoes=${zonas.map((z) => [z, z])} desligado=${!municipio}
        vazio=${municipio ? 'Escolha' : semMun} aoMudar=${(zona) => setSel({ uf: sel.uf, mun: sel.mun, zona })} />
      <${Select} rotulo="Seção" valor=${sel.secao} opcoes=${secoes.map((s) => [s, s])} desligado=${!sel.zona || !municipio}
        vazio=${sel.zona || municipio ? 'Escolha' : semMun} aoMudar=${(secao) => setSel({ ...sel, secao })} />
      <p class="status" role="status">${status}</p>
      <a class="tse" href=${ONDE_VOTAR} target="_blank" rel="noopener">Não sabe sua seção? Consulte no TSE</a>
    </section>
    ${municipio && chave && municipio.secoes[chave] && html`<${Secao} key=${`${sel.uf}/${sel.mun}/${chave}`} mun=${municipio} chave=${chave} />`}
    ${municipio && html`<${Ranking} key=${`${sel.uf}/${sel.mun}`} mun=${municipio} zonas=${zonas} chave=${chave} />`}
    </div>
    <footer>Dados: logs de urna do TSE (1º turno 2026, 1º e 2º turnos 2024). Hora local da urna. ${' '}<a href="https://github.com/dv-dev1/quehorasvoto">Código aberto</a></footer>`;
}

const raiz = document.getElementById('app');
raiz.replaceChildren();
render(html`<${App} />`, raiz);
