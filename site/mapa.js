import { html, useState, useEffect, useRef } from './vendor/preact-htm.mjs';
import { faixaFila, nome } from './calc.mjs';

export const UFS = [
  ['ac', 'Acre'], ['al', 'Alagoas'], ['ap', 'Amapá'], ['am', 'Amazonas'], ['ba', 'Bahia'], ['ce', 'Ceará'],
  ['df', 'Distrito Federal'], ['es', 'Espírito Santo'], ['go', 'Goiás'], ['ma', 'Maranhão'], ['mt', 'Mato Grosso'],
  ['ms', 'Mato Grosso do Sul'], ['mg', 'Minas Gerais'], ['pa', 'Pará'], ['pb', 'Paraíba'], ['pr', 'Paraná'],
  ['pe', 'Pernambuco'], ['pi', 'Piauí'], ['rj', 'Rio de Janeiro'], ['rn', 'Rio Grande do Norte'],
  ['rs', 'Rio Grande do Sul'], ['ro', 'Rondônia'], ['rr', 'Roraima'], ['sc', 'Santa Catarina'], ['sp', 'São Paulo'],
  ['se', 'Sergipe'], ['to', 'Tocantins'],
];

const LATERAIS = new Set(['rn', 'pb', 'pe', 'al', 'se', 'es', 'rj', 'df', 'sc']);
const cache = new Map();
const cor = (p) => `var(--${p == null ? 'sem-dado' : `f${faixaFila(p)}`})`;
const tinta = (p) => `var(--${p != null && faixaFila(p) >= 3 ? 'fundo' : 'texto'})`;
const percentual = (p) => p == null ? 'sem dados' : `${Math.round(p)}%`;
const percentualExato = (p) => p.toLocaleString('pt-BR', { maximumFractionDigits: 1 });

function carregar(arquivo) {
  if (!cache.has(arquivo)) cache.set(arquivo, fetch(`data/mapa/${arquivo}.json`).then((r) => {
    if (!r.ok) throw new Error(String(r.status));
    return r.json();
  }));
  return cache.get(arquivo);
}

export function Mapa({ sel, indice, aoUf, aoMun }) {
  const arquivo = sel.uf || 'br';
  const [estado, setEstado] = useState(null);
  const [hover, setHover] = useState(null);
  const [largura, setLargura] = useState(343);
  const ref = useRef(null);

  useEffect(() => {
    let vivo = true;
    setHover(null);
    Promise.all([carregar('br'), carregar(arquivo)]).then(
      ([br, mapa]) => { if (vivo) setEstado({ arquivo, br, mapa }); },
      () => { if (vivo) setEstado({ arquivo, erro: true }); },
    );
    return () => { vivo = false; };
  }, [arquivo]);

  useEffect(() => {
    const atualizar = () => setLargura(ref.current.getBoundingClientRect().width);
    atualizar();
    const observer = new ResizeObserver(atualizar);
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  const atual = estado?.arquivo === arquivo ? estado : null;
  const mapa = atual?.mapa;
  const uf = UFS.find(([codigo]) => codigo === sel.uf)?.[1] || sel.uf;
  const municipios = new Map(indice || []);
  const nomeLocal = (codigo) => sel.uf ? nome(municipios.get(codigo) || codigo) : UFS.find(([v]) => v === codigo)?.[1] || codigo.toUpperCase();
  const formas = mapa ? mapa.ufs || mapa.muns : {};
  const mapaLargura = Math.max(1, largura - (sel.uf ? 0 : 76));
  const altura = mapa ? mapaLargura * mapa.h / mapa.w : largura;
  const laterais = Object.entries(formas).filter(([codigo]) => !sel.uf && LATERAIS.has(codigo)).sort((a, b) => a[1].y - b[1].y);
  const alturaEtiquetas = Math.max(altura, laterais.length * 32 - 4);
  let anterior = -18;
  const etiquetas = laterais.map(([codigo, d]) => {
    const y = Math.max(d.y / mapa.h * altura, anterior + 32);
    anterior = y;
    return { codigo, d, y };
  });
  const excesso = Math.max(0, anterior - (alturaEtiquetas - 14));
  for (const etiqueta of etiquetas) etiqueta.y -= excesso;

  const acompanhar = (e, codigo) => {
    if (!matchMedia('(hover: hover)').matches) return;
    const caixa = ref.current.getBoundingClientRect();
    setHover({
      codigo,
      x: Math.max(8, Math.min(e.clientX - caixa.left + 16, caixa.width - 256)),
      y: Math.max(8, Math.min(e.clientY - caixa.top + 16, caixa.height - 116)),
    });
  };
  const visitar = (codigo) => { setHover(null); sel.uf ? aoMun(codigo) : aoUf(codigo); };
  const camada = (codigo) => codigo === sel.mun ? 2 : codigo === hover?.codigo ? 1 : 0;
  const caminhos = Object.entries(formas).sort(([a], [b]) => camada(a) - camada(b));
  const dadoHover = hover && formas[hover.codigo];

  return html`<section class="mapa-painel" aria-label="Explore a fila pelo mapa">
    ${sel.uf && html`<div class="mapa-topo">
      <button class="voltar" onClick=${() => aoUf(undefined)}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m10 3-5 5 5 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /></svg>Brasil
      </button>
      <h2>${uf}</h2>
      ${atual?.br && html`<span class="mapa-pct">· ${percentual(atual.br.ufs[sel.uf]?.pct)}${atual.br.ufs[sel.uf]?.pct != null ? ' pegaram fila' : ''}</span>`}
      ${sel.mun && html`<span class="mapa-municipio">${nomeLocal(sel.mun)} ${percentual(formas[sel.mun]?.pct)}</span>`}
    </div>`}
    <div class="mapa-corpo" ref=${ref} style=${{ minHeight: laterais.length ? `${laterais.length * 32 - 4}px` : undefined }} onPointerLeave=${() => setHover(null)}>
      ${!mapa ? html`<div class="mapa-espera" style=${{ aspectRatio: '1000 / 1000' }} role="status">
        ${atual?.erro ? 'Mapa indisponível. Use os campos abaixo.' : 'Carregando mapa…'}
      </div>` : html`
        <div class=${`mapa-area ${sel.uf ? '' : 'mapa-brasil'}`}>
          <svg key=${arquivo} class=${`mapa-svg ${sel.uf ? 'mapa-estado' : ''}`} viewBox=${`0 0 ${mapa.w} ${mapa.h}`} role="img"
            aria-label=${`Mapa ${sel.uf ? `de ${uf}, municípios` : 'do Brasil, estados'} pintados pela % de eleitores que pegaram fila no 1º turno de 2026`}>
            ${caminhos.map(([codigo, d]) => html`<path key=${codigo} d=${d.d} fill=${cor(d.pct)} fill-rule="evenodd"
              class=${`${codigo === sel.mun ? 'selecionado' : ''} ${codigo === hover?.codigo ? 'sobre' : ''}`}
              data-codigo=${codigo} stroke="var(--fundo)" stroke-width=${sel.uf ? '0.4' : '1'} vector-effect="non-scaling-stroke" aria-hidden="true"
              onClick=${() => visitar(codigo)} onPointerMove=${(e) => acompanhar(e, codigo)} />`)}
          </svg>
          ${!sel.uf && Object.entries(formas).filter(([codigo]) => !LATERAIS.has(codigo)).map(([codigo, d]) => html`
            <span class=${`mapa-rotulo ${largura < 520 ? 'compacto' : ''}`} style=${{ left: `${d.x / mapa.w * 100}%`, top: `${d.y / mapa.h * 100}%`, color: tinta(d.pct) }} aria-hidden="true">
              <strong>${codigo.toUpperCase()}</strong><span>${percentual(d.pct)}</span>
            </span>`)}
        </div>
        ${!sel.uf && html`
          <svg class="mapa-linhas" viewBox=${`0 0 ${largura} ${alturaEtiquetas}`} preserveAspectRatio="none" aria-hidden="true">
            ${etiquetas.map(({ d, y }) => html`<line x1=${d.x / mapa.w * mapaLargura} y1=${d.y / mapa.h * altura} x2=${mapaLargura + 12} y2=${y} stroke="var(--fio-forte)" stroke-width="1" />`)}
          </svg>
          ${etiquetas.map(({ codigo, d, y }) => html`<button class="mapa-etiqueta" style=${{ top: `${y}px`, background: cor(d.pct), color: tinta(d.pct) }}
            aria-label=${`${nomeLocal(codigo)}: ${d.pct == null ? 'sem dados de 2026' : `${percentualExato(d.pct)}% pegaram fila no 1º turno de 2026`}`}
            onClick=${() => visitar(codigo)} onPointerMove=${(e) => acompanhar(e, codigo)}>
            <strong>${codigo.toUpperCase()}</strong> ${percentual(d.pct)}
          </button>`)}
        `}
        ${dadoHover && html`<div class="mapa-tooltip" style=${{ left: `${hover.x}px`, top: `${hover.y}px` }} aria-hidden="true">
          <div class="mapa-tooltip-titulo"><span class="mapa-sigla">${(sel.uf || hover.codigo).toUpperCase()}</span><strong>${nomeLocal(hover.codigo)}</strong></div>
          <p>${dadoHover.pct == null ? 'sem dados de 2026' : `${percentualExato(dadoHover.pct)}% pegaram fila`}</p>
          ${dadoHover.pct != null && html`<span>no 1º turno de 2026</span>`}
        </div>`}
      `}
    </div>
    <div class="mapa-legenda">
      <p class="mapa-instrucao">${sel.uf ? 'Toque numa cidade ou escolha abaixo' : 'Toque num estado para ver as cidades'}</p>
      <p>% dos eleitores que pegaram fila · 1º turno 2026</p>
      <div class="mapa-escala">${['<10', '10', '15', '20', '25', '30+'].map((rotulo, i) => html`
        <span><i style=${{ background: `var(--f${i})` }}></i>${rotulo}</span>`)}
        <span class="mapa-sem-dado"><i></i>sem dados</span>
      </div>
    </div>
  </section>`;
}
