# quehorasvoto: plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use `subagent-driven-development` (recomendado) ou `executing-plans` para executar este plano tarefa por tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** site estático que mostra, por seção eleitoral, quantas pessoas votaram em cada bloco de meia hora (2026 1º turno e 2024) e o nível de fila, para o eleitor escolher o melhor horário no 2º turno de 25/10/2026.

**Arquitetura:** um script Python só com stdlib (`pipeline/quehorasvoto.py`) baixa da API do TSE o `aux.json` e o `log.jez` de cada seção, conta habilitações e gaps curtos por bloco de meia hora e grava um JSON por município em `site/data/<uf>/<mun>.json`. Uma GitHub Action roda o script para as 27 UFs e commita `site/data`. O frontend Preact + `htm` sem build lê esses JSONs e é servido como assets estáticos por um Cloudflare Worker.

**Stack:** Python ≥ 3.11 (stdlib: `urllib`, `zipfile`, `json`, `concurrent.futures`, `argparse`, `unittest`), Preact + htm via CDN ESM (`htm@3.1.1/preact/standalone`), `node --test` para a lógica pura do frontend, Wrangler (assets estáticos), GitHub Actions.

**Spec:** `/Users/dvdev/quehorasvoto/specs/2026-10-05-quehorasvoto.md` (decisões D1–D10 fechadas com o usuário; não reabrir).

## Restrições globais

- Pleitos: `3220` (ciclo `ele2026`, data `04/10/2026`), `452` (`ele2024`, `06/10/2024`), `453` (`ele2024`, `27/10/2024`, conferido em `config/pb/pb-p000453-cs.json`, campo `sec[].da`).
- Base da API: `https://resultados.tse.jus.br/oficial`. Config: `<base>/<ciclo>/arquivo-urna/<pleito>/config/<uf>/<uf>-p<pleito:06d>-cs.json`. Aux: `<base>/<ciclo>/arquivo-urna/<pleito>/dados/<uf>/<mun>/<zona>/<secao>/p<pleito:06d>-<uf>-m<mun>-z<zona>-s<secao>-aux.json`. Log: `.../<secao>/<hash>/<nm>` para `arq[].tp == "log"`.
- Arquivo inexistente no TSE responde **404** (conferido em 05/10/2026). Só 404 vale "sem dado". 403, 429, 5xx e erro de rede são transitórios: tentar de novo e, se persistir, levantar exceção (nunca virar "sem dado" em silêncio).
- O TSE anuncia `x-ratelimit-limit: 2000;w=1`. Paralelismo padrão: 8 por processo, `max-parallel: 8` na matriz.
- Log: zip com `logd.dat`, ISO-8859-1, TSV `DD/MM/AAAA HH:MM:SS \t nível \t id \t módulo \t mensagem \t mac`. Eventos com igualdade exata no campo mensagem: `Eleitor foi habilitado` e `O voto do eleitor foi computado`. Só linhas cuja data é a do pleito.
- Hora local, sem conversão de fuso (D5). Blocos de 30 min.
- Fila (D6): habilitação a menos de `GAP_FILA = 30` s do último voto computado. A primeira habilitação do dia nunca é fila. Níveis no frontend: `pct < 25` tranquilo, `25 ≤ pct ≤ 50` movimentado, `pct > 50` fila.
- Urna com mais de um hash no `aux.json`: usar **a união dos logs de todos os hashes, sem linhas repetidas**, ordenada por horário. Motivo: urna substituída tem os votos divididos entre os logs; reenvio do mesmo arquivo gera linhas idênticas, que a deduplicação descarta. Pegar só o último hash perderia os votos da urna original.
- Seção sem `aux.json`, sem arquivo `tp == "log"`, com zip corrompido ou sem nenhuma habilitação na data: valor `null` para aquele pleito. Nunca derruba o município.
- Pipeline: só stdlib. Um arquivo: `pipeline/quehorasvoto.py`. Testes em `pipeline/test_quehorasvoto.py` com `unittest`, sem rede; fixture latin1 em `pipeline/fixtures/`.
- Frontend sem build e sem `package.json`. Lógica pura em `site/calc.mjs`, testada por `node --test test/calc.test.mjs`.
- Worker só com assets estáticos; nada de `fetch` ao TSE em runtime.
- Limites do Workers Free: 20.000 arquivos e 25 MiB por arquivo.
- Repo público `dv-dev1/quehorasvoto`, MIT. Comentário no código só para o porquê.
- Prazo: no ar até 18/10/2026.
- Commits, `git init`, `gh repo create`, `npx wrangler deploy` e `gh workflow run` são do agente pai. O executor (Sol) só escreve na árvore de trabalho e roda os testes.

## Esquema dos dados

`site/data/<uf>/index.json`: municípios do 3220 ordenados pelo nome sem acento.

```json
[["19313", "BANANEIRAS"], ["20516", "JOÃO PESSOA"]]
```

`site/data/<uf>/<mun>.json`:

```json
{
  "uf": "pb", "cd": "19313", "nm": "BANANEIRAS",
  "secoes": {
    "0014/0001": {
      "3220": {"inicio": "08:00", "eleitores": [17, 9, 15], "fila": [3, 3, 4]},
      "452": {"inicio": "08:00", "eleitores": [12, 10, 8], "fila": [2, 1, 0]},
      "453": null
    }
  },
  "ranking": [["0014/0001", 38, 271]]
}
```

- Pleito ausente na seção: a seção não existia na config daquele pleito (renumeração, município sem 2º turno). Pleito com `null`: existia, mas sem dado.
- `fila` é a **contagem** de eleitores que pegaram fila no bloco, não o percentual. O frontend calcula `pct = round(100 * fila / eleitores)`. Contagem é exata, ocupa o mesmo espaço e permite somar o dia inteiro para o ranking.
- `ranking`: `[chave, pct_fila_do_dia, eleitores_do_dia]` do pleito `3220`, ordenado por fração exata decrescente, desempate por mais eleitores e depois pela chave. Seções sem dado em 2026 ficam fora.
- JSON compacto (`separators=(",", ":")`, `ensure_ascii=False`). Estimativa: ~400 bytes por seção, capital de SP perto de 12 MB, ~5.600 arquivos no total.

## Revisão: onde mais pode quebrar

1. **Urna substituída (dois hashes)**: os votos dos dois logs entram uma vez só; reenvio idêntico não dobra a contagem. Teste na Tarefa 2.
2. **Seção sem log, zip corrompido ou aux 404**: valor `null`, o município sai inteiro, e o site mostra "sem dado" em vez de quebrar. Testes nas Tarefas 2 e 6.
3. **Falha de rede transitória**: tenta de novo com espera exponencial; se persistir, o município não é gravado e a próxima rodada o refaz. Nunca grava "sem dado" por causa de 503. Testes nas Tarefas 2 e 9.
4. **Config ausente** (DF não tem eleição em 2024; AC e boa parte dos municípios não têm 2º turno): `carregar_cs` devolve `{}` e o pleito some do JSON sem erro. Teste na Tarefa 3.
5. **Hash da URL inválido ou malicioso** (`#../../x`, `#PB/abc`): é ignorado a partir da primeira parte inválida, e nada fora de `data/<uf>/<mun>.json` é buscado. Teste na Tarefa 6.

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `pipeline/quehorasvoto.py` | parser, download, montagem do município, CLI `secao` / `municipio` / `uf` |
| `pipeline/test_quehorasvoto.py` | testes `unittest` do pipeline, sem rede |
| `pipeline/fixtures/logd_trecho.dat` | trecho de log latin1 com casos de borda |
| `site/index.html` | casca da página |
| `site/app.js` | componentes Preact (selects, gráfico, cards, ranking) |
| `site/calc.mjs` | lógica pura: níveis, melhor bloco, hash, ranking |
| `site/style.css` | tema escuro |
| `site/data/<uf>/*.json` | dados gerados (commitados) |
| `test/calc.test.mjs` | testes `node --test` do `calc.mjs` |
| `wrangler.jsonc` | Worker só com assets |
| `.github/workflows/ci.yml` | ruff, testes Python em 3.11 e 3.13, teste JS, checagem de stdlib |
| `.github/workflows/dados.yml` | coleta por UF e commit de `site/data` |
| `pyproject.toml`, `LICENSE`, `README.md`, `.gitignore` | repo público |

## Ordem e cronograma

```
Tarefa 0 (pai) → 1 parser → 2 seção → 3 município ──→ 6 calc.mjs → 7 site → 8 deploy do recorte (pai) → 9 comando uf → 10 dados.yml → 12 rodada nacional (pai)
                                       ├→ 4 calibração (paralela a 5–7)
                                       └→ 5 CI + README (paralela a 6–7)
                                                       11 passe de UI com impeccable (pai, depois da 8, antes da 12)
```

| Até | Marco |
|---|---|
| 07/10 | Tarefas 0–3: Bananeiras gerada a partir do TSE real |
| 09/10 | Tarefas 4–8: recorte vertical no ar em `workers.dev` |
| 11/10 | Tarefas 9–11: coleta pronta para as 27 UFs, UI polida |
| 12/10 | Disparo da coleta nacional (leva horas; pode precisar de 2 ou 3 rodadas) |
| 16/10 | Dados completos e deploy final |
| 18/10 | Folga |

---

### Tarefa 0 (pai): repositório

**Executor:** agente pai. Faixa vermelha, mostrar `## PLAN` antes.

- [ ] **Passo 1:** `cd /Users/dvdev/quehorasvoto && git init -b main`
- [ ] **Passo 2:** criar `.gitignore`:

```
__pycache__/
*.pyc
*.tmp
.wrangler/
node_modules/
```

- [ ] **Passo 3:** `git add .gitignore specs && git commit -m "chore: spec e plano"`
- [ ] **Passo 4:** `gh repo create dv-dev1/quehorasvoto --public --source . --push`

---

### Tarefa 1: parser de eventos e blocos

**Executor:** Sol.

**Arquivos:**
- Criar: `pipeline/quehorasvoto.py`
- Criar: `pipeline/fixtures/logd_trecho.dat`
- Criar: `pipeline/test_quehorasvoto.py`
- Criar: `pyproject.toml`

**Interfaces:**
- Consome: nada.
- Produz:
  - `PLEITOS: dict[str, tuple[str, str]]` → `{"3220": ("ele2026", "04/10/2026"), "452": ("ele2024", "06/10/2024"), "453": ("ele2024", "27/10/2024")}`
  - `HAB = "Eleitor foi habilitado"`, `COMP = "O voto do eleitor foi computado"`, `GAP_FILA = 30`
  - `eventos(logs: list[str], data: str) -> list[tuple[int, bool]]`: `(segundos desde 00:00, é_habilitação)`, sem linhas repetidas entre os logs, ordenado por horário (ordem estável)
  - `blocos(ev: list[tuple[int, bool]], gap: int = GAP_FILA) -> dict | None`: `{"inicio": "HH:MM", "eleitores": [int], "fila": [int]}`, do bloco da primeira habilitação ao da última, com zeros no meio; `None` se não há habilitação

- [ ] **Passo 1: gerar a fixture** (tabs e latin1 exatos, por isso via script)

```bash
mkdir -p pipeline/fixtures && python3 - <<'EOF'
from pathlib import Path
L = [
    ("21/09/2026 08:15:07", "LOGD", "Início das operações do logd"),
    ("04/10/2026 07:15:42", "GAP", "Mídia de votação gerada pelo computador"),
    ("04/10/2026 08:01:06", "VOTA", "Eleitor foi habilitado"),
    ("04/10/2026 08:03:13", "VOTA", "O voto do eleitor foi computado"),
    ("04/10/2026 08:03:58", "VOTA", "Eleitor foi habilitado"),
    ("04/10/2026 08:05:00", "VOTA", "O voto do eleitor foi computado"),
    ("04/10/2026 08:05:10", "VOTA", "Eleitor foi habilitado"),
    ("04/10/2026 08:06:00", "VOTA", "Mesário 025964461210 habilitou o eleitor"),
    ("04/10/2026 08:29:50", "VOTA", "O voto do eleitor foi computado"),
    ("04/10/2026 08:30:19", "VOTA", "Eleitor foi habilitado"),
    ("04/10/2026 08:31:00", "VOTA", "O voto do eleitor foi computado"),
    ("04/10/2026 08:31:30", "VOTA", "Eleitor foi habilitado"),
    ("04/10/2026 08:33:00", "VOTA", "O voto do eleitor foi computado"),
    ("04/10/2026 09:40:00", "VOTA", "Eleitor foi habilitado"),
    ("04/10/2026 09:41:00", "VOTA", "O voto do eleitor foi computado"),
    ("05/10/2026 10:00:00", "VOTA", "Eleitor foi habilitado"),
]
linhas = [f"{d}\tINFO\t02168890\t{m}\t{msg}\t{i:016X}" for i, (d, m, msg) in enumerate(L)]
linhas.insert(15, "linha quebrada sem tabulação")
Path("pipeline/fixtures/logd_trecho.dat").write_bytes(("\n".join(linhas) + "\n").encode("latin1"))
EOF
```

O que a fixture cobre: linhas de outra data (21/09 e 05/10) ignoradas; acento em latin1; mensagem parecida (`Mesário ... habilitou o eleitor`) que não conta; linha sem tabulação; gap de 45 s (não é fila), 10 s (fila), 29 s (fila), exatamente 30 s (não é fila); bloco vazio às 09:00. Resultado esperado: `{"inicio": "08:00", "eleitores": [3, 2, 0, 1], "fila": [1, 1, 0, 0]}`.

- [ ] **Passo 2: escrever os testes**

```python
import unittest
from pathlib import Path

import quehorasvoto as q

FIXTURE = (Path(__file__).parent / "fixtures" / "logd_trecho.dat").read_bytes().decode("latin1")
DATA = "04/10/2026"


class TestParser(unittest.TestCase):
    def test_blocos_da_fixture(self):
        r = q.blocos(q.eventos([FIXTURE], DATA), gap=30)
        self.assertEqual(r, {"inicio": "08:00", "eleitores": [3, 2, 0, 1], "fila": [1, 1, 0, 0]})

    def test_gap_de_30s_nao_e_fila(self):
        self.assertEqual(q.blocos(q.eventos([FIXTURE], DATA), gap=31)["fila"], [1, 2, 0, 0])

    def test_eventos_filtra_data_e_mensagem_exata(self):
        ev = q.eventos([FIXTURE], DATA)
        self.assertEqual(len(ev), 12)
        self.assertEqual(sum(h for _, h in ev), 6)
        self.assertEqual(ev[0], (8 * 3600 + 66, True))

    def test_logs_repetidos_nao_dobram(self):
        metade = "\n".join(FIXTURE.splitlines()[:8])
        self.assertEqual(q.eventos([metade, FIXTURE], DATA), q.eventos([FIXTURE], DATA))

    def test_logs_de_urnas_diferentes_somam(self):
        linhas = FIXTURE.splitlines()
        a, b = "\n".join(linhas[:9]), "\n".join(linhas[9:])
        self.assertEqual(q.eventos([a, b], DATA), q.eventos([FIXTURE], DATA))

    def test_computado_e_habilitado_no_mesmo_segundo_e_fila(self):
        self.assertEqual(q.blocos([(100, True), (200, False), (200, True)])["fila"], [1])

    def test_sem_habilitacao_e_none(self):
        self.assertIsNone(q.blocos([]))
        self.assertIsNone(q.blocos(q.eventos([FIXTURE], "01/01/2000")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Passo 3: rodar e ver falhar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `ModuleNotFoundError: No module named 'quehorasvoto'` ou `AttributeError`.

- [ ] **Passo 4: implementar o mínimo**

```python
"""Quantas pessoas votaram em cada meia hora de cada seção, a partir dos logs de urna do TSE."""

PLEITOS = {
    "3220": ("ele2026", "04/10/2026"),
    "452": ("ele2024", "06/10/2024"),
    "453": ("ele2024", "27/10/2024"),
}
HAB = "Eleitor foi habilitado"
COMP = "O voto do eleitor foi computado"
GAP_FILA = 30
BLOCO = 1800


def eventos(logs, data):
    # União sem repetição: urna substituída divide os votos entre os logs, e reenvio repete linhas.
    vistas, ev = set(), []
    for texto in logs:
        for linha in texto.splitlines():
            if linha in vistas:
                continue
            vistas.add(linha)
            p = linha.split("\t")
            if len(p) < 5 or not p[0].startswith(data) or p[4] not in (HAB, COMP):
                continue
            h, m, s = map(int, p[0][11:19].split(":"))
            ev.append((h * 3600 + m * 60 + s, p[4] == HAB))
    ev.sort(key=lambda e: e[0])
    return ev


def blocos(ev, gap=GAP_FILA):
    habs, ultimo = [], None
    for t, hab in ev:
        if not hab:
            ultimo = t
        else:
            habs.append((t, ultimo is not None and t - ultimo < gap))
    if not habs:
        return None
    ini = habs[0][0] // BLOCO
    n = habs[-1][0] // BLOCO - ini + 1
    eleitores, fila = [0] * n, [0] * n
    for t, f in habs:
        eleitores[t // BLOCO - ini] += 1
        fila[t // BLOCO - ini] += f
    minutos = ini * 30
    return {"inicio": f"{minutos // 60:02d}:{minutos % 60:02d}", "eleitores": eleitores, "fila": fila}
```

`pyproject.toml`:

```toml
[project]
name = "quehorasvoto"
version = "0.1.0"
description = "Melhor horário para votar na sua seção, a partir dos logs de urna do TSE"
requires-python = ">=3.11"
license = "MIT"

[tool.ruff]
line-length = 110
target-version = "py311"
```

- [ ] **Passo 5: rodar e ver passar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `OK` com 7 testes.

- [ ] **Passo 6: prova do vermelho.** Trocar `t - ultimo < gap` por `t - ultimo <= gap`, rodar: `test_blocos_da_fixture` falha (`fila [1, 2, 0, 0]`). Desfazer, rodar: `OK`.

- [ ] **Passo 7 (pai): commit** `git add pipeline pyproject.toml && git commit -m "feat: parser de eventos e blocos de meia hora"`

---

### Tarefa 2: download e processamento de uma seção

**Executor:** Sol.

**Arquivos:**
- Modificar: `pipeline/quehorasvoto.py`
- Modificar: `pipeline/test_quehorasvoto.py`

**Interfaces:**
- Consome: `PLEITOS`, `eventos`, `blocos` (Tarefa 1).
- Produz:
  - `url_cs(pleito, uf) -> str`, `url_secao(pleito, uf, mun, zona, secao) -> str` (diretório da seção, sem barra no fim), `url_aux(pleito, uf, mun, zona, secao) -> str`
  - `baixar(url: str, tentativas: int = 4, espera: float = 1.0) -> bytes | None`: `None` só para 404; outros erros tentam de novo com espera `espera * 2**n` e levantam a última exceção
  - `ler_jez(dados: bytes) -> str | None`: `None` para zip corrompido ou sem `logd.dat`
  - `logs_da_secao(pleito, uf, mun, zona, secao, baixar=baixar) -> list[str]`
  - `processar_secao(pleito, uf, mun, zona, secao, baixar=baixar) -> dict | None`
  - `main(argv: list[str] | None = None) -> int` com o subcomando `secao [--pleito P] uf mun zona secao`, que imprime o JSON (ou `null`)

- [ ] **Passo 1: escrever os testes** (acrescentar ao arquivo; imports no topo)

```python
import io
import json
import urllib.error
import zipfile
from unittest import mock


def jez(texto):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("logd.dat", texto.encode("latin1"))
    return buf.getvalue()


def fake_baixar(mapa):
    def baixar(url):
        v = mapa.get(url)
        if isinstance(v, Exception):
            raise v
        return v
    return baixar


def aux(*hashes):
    return json.dumps({"hashes": [
        {"hash": h, "arq": [{"nm": f"{h}-log.jez", "tp": "log"}, {"nm": f"{h}-bu.dat", "tp": "bu"}]}
        for h in hashes
    ]}).encode()


SEC = ("3220", "pb", "19313", "0014", "0001")
DIR = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/pb/19313/0014/0001"
ESPERADO = {"inicio": "08:00", "eleitores": [3, 2, 0, 1], "fila": [1, 1, 0, 0]}


class TestSecao(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(q.url_secao(*SEC), DIR)
        self.assertEqual(q.url_aux(*SEC), DIR + "/p003220-pb-m19313-z0014-s0001-aux.json")
        self.assertEqual(
            q.url_cs("452", "pb"),
            "https://resultados.tse.jus.br/oficial/ele2024/arquivo-urna/452/config/pb/pb-p000452-cs.json",
        )

    def test_secao_com_um_hash(self):
        b = fake_baixar({q.url_aux(*SEC): aux("h1"), DIR + "/h1/h1-log.jez": jez(FIXTURE)})
        self.assertEqual(q.processar_secao(*SEC, baixar=b), ESPERADO)

    def test_dois_hashes_somam_sem_dobrar(self):
        linhas = FIXTURE.splitlines()
        b = fake_baixar({
            q.url_aux(*SEC): aux("h1", "h2"),
            DIR + "/h1/h1-log.jez": jez("\n".join(linhas[:9])),
            DIR + "/h2/h2-log.jez": jez("\n".join(linhas[5:])),
        })
        self.assertEqual(q.processar_secao(*SEC, baixar=b), ESPERADO)

    def test_sem_aux_e_none(self):
        self.assertIsNone(q.processar_secao(*SEC, baixar=fake_baixar({})))

    def test_sem_arquivo_de_log_e_none(self):
        so_bu = json.dumps({"hashes": [{"hash": "h1", "arq": [{"nm": "x-bu.dat", "tp": "bu"}]}]}).encode()
        self.assertIsNone(q.processar_secao(*SEC, baixar=fake_baixar({q.url_aux(*SEC): so_bu})))

    def test_zip_corrompido_e_none(self):
        b = fake_baixar({q.url_aux(*SEC): aux("h1"), DIR + "/h1/h1-log.jez": b"nao e zip"})
        self.assertIsNone(q.processar_secao(*SEC, baixar=b))

    def test_erro_de_rede_propaga(self):
        b = fake_baixar({q.url_aux(*SEC): urllib.error.URLError("timeout")})
        with self.assertRaises(urllib.error.URLError):
            q.processar_secao(*SEC, baixar=b)


def http_erro(codigo):
    return urllib.error.HTTPError("u", codigo, "x", {}, None)


class TestBaixar(unittest.TestCase):
    @mock.patch("quehorasvoto.urllib.request.urlopen")
    def test_404_e_none_sem_retentar(self, urlopen):
        urlopen.side_effect = [http_erro(404)]
        self.assertIsNone(q.baixar("u", espera=0))
        self.assertEqual(urlopen.call_count, 1)

    @mock.patch("quehorasvoto.urllib.request.urlopen")
    def test_503_retenta(self, urlopen):
        urlopen.side_effect = [http_erro(503), io.BytesIO(b"ok")]
        self.assertEqual(q.baixar("u", espera=0), b"ok")

    @mock.patch("quehorasvoto.urllib.request.urlopen")
    def test_403_persistente_levanta(self, urlopen):
        urlopen.side_effect = [http_erro(403)] * 4
        with self.assertRaises(urllib.error.HTTPError):
            q.baixar("u", espera=0)
        self.assertEqual(urlopen.call_count, 4)
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `AttributeError: module 'quehorasvoto' has no attribute 'url_secao'` nos testes novos.

- [ ] **Passo 3: implementar**

```python
import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile

BASE = "https://resultados.tse.jus.br/oficial"
UA = {"User-Agent": "quehorasvoto (+https://github.com/dv-dev1/quehorasvoto)"}


def _raiz(pleito):
    return f"{BASE}/{PLEITOS[pleito][0]}/arquivo-urna/{pleito}"


def url_cs(pleito, uf):
    return f"{_raiz(pleito)}/config/{uf}/{uf}-p{int(pleito):06d}-cs.json"


def url_secao(pleito, uf, mun, zona, secao):
    return f"{_raiz(pleito)}/dados/{uf}/{mun}/{zona}/{secao}"


def url_aux(pleito, uf, mun, zona, secao):
    return f"{url_secao(pleito, uf, mun, zona, secao)}/p{int(pleito):06d}-{uf}-m{mun}-z{zona}-s{secao}-aux.json"


def baixar(url, tentativas=4, espera=1.0):
    # Só 404 é "não existe": 403/429/5xx do CDN podem ser throttling e não podem virar "sem dado".
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            erro = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            erro = e
        if n < tentativas - 1:
            time.sleep(espera * 2**n)
    raise erro


def ler_jez(dados):
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            return z.read("logd.dat").decode("latin1")
    except (zipfile.BadZipFile, KeyError):
        return None


def logs_da_secao(pleito, uf, mun, zona, secao, baixar=baixar):
    dados_aux = baixar(url_aux(pleito, uf, mun, zona, secao))
    if dados_aux is None:
        return []
    pasta, logs = url_secao(pleito, uf, mun, zona, secao), []
    for h in json.loads(dados_aux).get("hashes", []):
        for a in h.get("arq", []):
            if a.get("tp") != "log":
                continue
            dados = baixar(f"{pasta}/{h['hash']}/{a['nm']}")
            texto = ler_jez(dados) if dados else None
            if texto:
                logs.append(texto)
    return logs


def processar_secao(pleito, uf, mun, zona, secao, baixar=baixar):
    logs = logs_da_secao(pleito, uf, mun, zona, secao, baixar)
    return blocos(eventos(logs, PLEITOS[pleito][1])) if logs else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="quehorasvoto")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("secao", help="blocos de meia hora de uma seção")
    s.add_argument("--pleito", choices=list(PLEITOS), default="3220")
    for nome in ("uf", "mun", "zona", "secao"):
        s.add_argument(nome)
    a = ap.parse_args(argv)
    if a.cmd == "secao":
        print(json.dumps(processar_secao(a.pleito, a.uf.lower(), a.mun, a.zona, a.secao)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `OK`.

- [ ] **Passo 5: prova do vermelho.** Em `baixar`, trocar `if e.code == 404` por `if e.code in (403, 404)`: `test_403_persistente_levanta` falha. Desfazer.

- [ ] **Passo 6: critério de aceite #1 (rede real)**

Run:
```bash
python3 pipeline/quehorasvoto.py secao --pleito 3220 pb 19313 0014 0001 \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['inicio'], len(d['eleitores']), sum(d['eleitores']), sum(d['fila']))"
```
Esperado: `08:00 18 271 104`.

- [ ] **Passo 7 (pai): commit** `git commit -am "feat: download e processamento de uma seção"`

---

### Tarefa 3: município inteiro e índice da UF

**Executor:** Sol.

**Arquivos:**
- Modificar: `pipeline/quehorasvoto.py`
- Modificar: `pipeline/test_quehorasvoto.py`
- Criar (gerados): `site/data/pb/19313.json`, `site/data/pb/index.json`

**Interfaces:**
- Consome: `processar_secao`, `baixar`, `url_cs`, `PLEITOS`, `main` (Tarefa 2).
- Produz:
  - `carregar_cs(pleito, uf, baixar=baixar) -> dict` (`{}` se 404)
  - `secoes_cs(cs: dict, mun: str) -> tuple[str | None, list[str]]` → `(nome, ["zona/secao", ...])`
  - `ranking(secoes: dict, pleito: str = "3220") -> list[list]` → `[[chave, pct_int, eleitores], ...]`
  - `montar_municipio(uf, mun, configs: dict[str, dict], baixar=baixar, paralelo=8) -> dict` (esquema da seção "Esquema dos dados"); `ValueError` se o município não está em nenhuma config
  - `indice(cs: dict) -> list[list[str]]` → `[[cd, nm], ...]` ordenado pelo nome sem acento
  - `escrever_json(caminho: Path, obj) -> None`: grava em `.tmp` e faz `os.replace`
  - subcomando `municipio uf mun [--saida site/data] [--paralelo 8]`, que grava `<saida>/<uf>/<mun>.json` e `<saida>/<uf>/index.json`

- [ ] **Passo 1: escrever os testes**

```python
import tempfile


def cs(*municipios):
    return {"abr": [{"cd": "pb", "mu": [
        {"cd": cd, "nm": nm, "zon": [{"cd": z, "sec": [{"ns": s} for s in secs]} for z, secs in zonas.items()]}
        for cd, nm, zonas in municipios
    ]}]}


LOG_B = "\n".join(f"04/10/2026 {h}\tINFO\t1\tVOTA\t{m}\t{i:X}" for i, (h, m) in enumerate([
    ("08:00:00", q.HAB), ("08:01:00", q.COMP), ("08:01:05", q.HAB),
    ("08:02:00", q.COMP), ("08:02:10", q.HAB), ("08:03:00", q.COMP),
]))


def mapa_bananeiras():
    def sec(pleito, zona, secao, log):
        d = q.url_secao(pleito, "pb", "19313", zona, secao)
        return {q.url_aux(pleito, "pb", "19313", zona, secao): aux("h"), d + "/h/h-log.jez": jez(log)}
    return {
        **sec("3220", "0001", "0001", FIXTURE),
        **sec("3220", "0001", "0002", LOG_B),
        **sec("452", "0001", "0001", FIXTURE.replace("04/10/2026", "06/10/2024")),
    }


CONFIGS = {
    "3220": cs(("19313", "BANANEIRAS", {"0001": ["0001", "0002"]})),
    "452": cs(("19313", "BANANEIRAS", {"0001": ["0001", "0003"]})),
    "453": {},
}


class TestMunicipio(unittest.TestCase):
    def test_montar(self):
        m = q.montar_municipio("pb", "19313", CONFIGS, baixar=fake_baixar(mapa_bananeiras()), paralelo=2)
        self.assertEqual((m["uf"], m["cd"], m["nm"]), ("pb", "19313", "BANANEIRAS"))
        self.assertEqual(list(m["secoes"]), ["0001/0001", "0001/0002", "0001/0003"])
        self.assertEqual(m["secoes"]["0001/0001"], {"3220": ESPERADO, "452": ESPERADO})
        self.assertEqual(m["secoes"]["0001/0002"], {"3220": {"inicio": "08:00", "eleitores": [3], "fila": [2]}})
        self.assertEqual(m["secoes"]["0001/0003"], {"452": None})
        self.assertEqual(m["ranking"], [["0001/0002", 67, 3], ["0001/0001", 33, 6]])

    def test_municipio_inexistente(self):
        with self.assertRaises(ValueError):
            q.montar_municipio("pb", "99999", CONFIGS, baixar=fake_baixar({}))

    def test_cs_ausente_e_vazio(self):
        self.assertEqual(q.carregar_cs("452", "df", baixar=fake_baixar({})), {})

    def test_indice_ordena_sem_acento(self):
        c = cs(("3", "ZABELÊ", {}), ("1", "ÁGUA BRANCA", {}), ("2", "BANANEIRAS", {}))
        self.assertEqual(q.indice(c), [["1", "ÁGUA BRANCA"], ["2", "BANANEIRAS"], ["3", "ZABELÊ"]])

    def test_escrever_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pb" / "19313.json"
            q.escrever_json(p, {"nm": "JOÃO"})
            self.assertEqual(p.read_text(encoding="utf-8"), '{"nm":"JOÃO"}')
            self.assertEqual(list(p.parent.iterdir()), [p])
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `AttributeError: module 'quehorasvoto' has no attribute 'montar_municipio'`.

- [ ] **Passo 3: implementar** (imports novos no topo: `os`, `unicodedata`, `from concurrent.futures import ThreadPoolExecutor`, `from pathlib import Path`)

```python
def carregar_cs(pleito, uf, baixar=baixar):
    # DF não tem eleição em 2024 e muitos estados não têm 2º turno: a config simplesmente não existe.
    dados = baixar(url_cs(pleito, uf))
    return json.loads(dados) if dados else {}


def _municipios(cs):
    return (cs.get("abr") or [{}])[0].get("mu", [])


def secoes_cs(cs, mun):
    for m in _municipios(cs):
        if m["cd"] == mun:
            return m["nm"], [f"{z['cd']}/{s['ns']}" for z in m["zon"] for s in z["sec"]]
    return None, []


def ranking(secoes, pleito="3220"):
    linhas = []
    for chave, por_pleito in secoes.items():
        d = por_pleito.get(pleito)
        if d:
            n = sum(d["eleitores"])
            linhas.append((sum(d["fila"]) / n, n, chave))
    linhas.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [[chave, round(100 * r), n] for r, n, chave in linhas]


def montar_municipio(uf, mun, configs, baixar=baixar, paralelo=8):
    nome, tarefas = None, []
    for pleito, cs in configs.items():
        nm, chaves = secoes_cs(cs, mun)
        nome = nome or nm
        tarefas += [(pleito, chave) for chave in chaves]
    if nome is None:
        raise ValueError(f"município {uf}/{mun} não está em nenhuma config")
    with ThreadPoolExecutor(paralelo) as ex:
        resultados = ex.map(lambda t: processar_secao(t[0], uf, mun, *t[1].split("/"), baixar=baixar), tarefas)
        secoes = {}
        for (pleito, chave), r in zip(tarefas, resultados):
            secoes.setdefault(chave, {})[pleito] = r
    secoes = dict(sorted(secoes.items()))
    return {"uf": uf, "cd": mun, "nm": nome, "secoes": secoes, "ranking": ranking(secoes)}


def _sem_acento(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()


def indice(cs):
    return sorted(([m["cd"], m["nm"]] for m in _municipios(cs)), key=lambda x: _sem_acento(x[1]))


def escrever_json(caminho, obj):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, caminho)
```

`configs` é montado na ordem de `PLEITOS`, então o nome vem do 3220. No `main`, acrescentar:

```python
    m = sub.add_parser("municipio", help="JSON de um município")
    m.add_argument("uf")
    m.add_argument("mun")
    m.add_argument("--saida", default="site/data")
    m.add_argument("--paralelo", type=int, default=8)
```

```python
    if a.cmd == "municipio":
        uf = a.uf.lower()
        configs = {p: carregar_cs(p, uf) for p in PLEITOS}
        destino = Path(a.saida) / uf
        escrever_json(destino / f"{a.mun}.json", montar_municipio(uf, a.mun, configs, paralelo=a.paralelo))
        escrever_json(destino / "index.json", indice(configs["3220"]))
        print(destino / f"{a.mun}.json")
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `OK`.

- [ ] **Passo 5: prova do vermelho.** Inverter o sinal em `ranking` (`x[0]` em vez de `-x[0]`): `test_montar` falha. Desfazer.

- [ ] **Passo 6: critério de aceite #3 (rede real)**

```bash
python3 pipeline/quehorasvoto.py municipio pb 19313 --saida site/data
python3 - <<'EOF'
import json
d = json.load(open("site/data/pb/19313.json", encoding="utf-8"))
s = d["secoes"]
print(d["nm"], len(s), {p: sum(p in v for v in s.values()) for p in ("3220", "452", "453")},
      {p: sum(v.get(p, 0) is None for v in s.values()) for p in ("3220", "452")})
r = [x[1] for x in d["ranking"]]
print(r == sorted(r, reverse=True), s["0014/0001"]["3220"]["eleitores"][:3])
EOF
```
Esperado: primeira linha `BANANEIRAS <n> {'3220': <a>, '452': <b>, '453': 0} {...}` (conferir `<a>` e `<b>` contra o número de seções do cs de cada pleito); segunda linha `True [17, 9, 15]`. Colar a saída no relatório da tarefa.

- [ ] **Passo 7 (pai): commit** `git add pipeline site/data && git commit -m "feat: JSON por município e índice da UF"`

---

### Tarefa 4: calibração dos limites de fila

**Executor:** Sol (rede real). Pode rodar em paralelo às Tarefas 5–7.

**Arquivos:**
- Modificar: `specs/2026-10-05-quehorasvoto.md` (nova seção `## Calibração`)
- Modificar, só se a regra abaixo mandar: `pipeline/quehorasvoto.py` (`GAP_FILA`) e regenerar `site/data/pb/19313.json`

**Interfaces:**
- Consome: `carregar_cs`, `logs_da_secao`, `eventos`, `blocos`, `PLEITOS` (Tarefas 2–3).
- Produz: valores finais de `GAP_FILA` e dos limites 25/50, registrados na spec. A Tarefa 6 lê os limites dali.

- [ ] **Passo 1: rodar a amostra** (21 seções: 7 UFs × maior município (2 seções) + menor município (1 seção))

```bash
python3 - <<'EOF'
import collections, statistics, sys
sys.path.insert(0, "pipeline")
import quehorasvoto as q

def tam(m):
    return sum(len(z["sec"]) for z in m["zon"])

amostra = []
for uf in ["sp", "ba", "am", "rs", "ac", "pb", "go"]:
    mus = q.carregar_cs("3220", uf)["abr"][0]["mu"]
    g, p = max(mus, key=tam), min(mus, key=tam)
    z = g["zon"][0]
    amostra += [(uf, g["cd"], z["cd"], z["sec"][0]["ns"]), (uf, g["cd"], z["cd"], z["sec"][len(z["sec"]) // 2]["ns"])]
    amostra.append((uf, p["cd"], p["zon"][0]["cd"], p["zon"][0]["sec"][0]["ns"]))

hist, pcts = collections.Counter(), []
for uf, mun, zona, secao in amostra:
    ev = q.eventos(q.logs_da_secao("3220", uf, mun, zona, secao), q.PLEITOS["3220"][1])
    gaps, ultimo = [], None
    for t, hab in ev:
        if not hab:
            ultimo = t
        elif ultimo is not None:
            gaps.append(t - ultimo)
    hist.update(min(g // 5 * 5, 120) for g in gaps)
    b = q.blocos(ev)
    if not b:
        print(f"{uf} {mun} {zona}/{secao}: sem dado")
        continue
    n, f = sum(b["eleitores"]), sum(b["fila"])
    print(f"{uf} {mun} {zona}/{secao}: {n} eleitores, {round(100 * f / n)}% fila, gap mediano {statistics.median(gaps) if gaps else '-'} s")
    pcts += [round(100 * fi / ni) for ni, fi in zip(b["eleitores"], b["fila"]) if ni >= 5]

print("histograma de gaps (início do balde de 5 s: contagem):", sorted(hist.items()))
c = statistics.quantiles(pcts, n=20)
print(f"pct por bloco (blocos com 5+ eleitores, n={len(pcts)}): p25={c[4]} p50={c[9]} p75={c[14]} p85={c[16]} p90={c[17]}")
EOF
```

- [ ] **Passo 2: aplicar a regra de decisão**
  - `GAP_FILA`: se o histograma tiver um vale nítido entre 15 s e 60 s (balde com menos de 70% da contagem dos dois vizinhos), `GAP_FILA` = início desse balde. Senão, fica 30.
  - Limites: ficam 25/50 se `15 ≤ p50 ≤ 40` e `p90 > 50`. Senão, `movimentado = p50` e `fila = p85`, os dois arredondados ao múltiplo de 5 mais próximo.

- [ ] **Passo 3: registrar na spec**, antes de `## Critério de aceite`:

```markdown
## Calibração (<data>)

<saída do Passo 1, num bloco de código>

Decisão: GAP_FILA = <valor> s; tranquilo < <x>%, movimentado <x>–<y>%, fila > <y>%. <uma frase do porquê, citando o histograma e os percentis>
```

- [ ] **Passo 4: se `GAP_FILA` mudou**, trocar a constante, rodar `python3 -m unittest discover -s pipeline` (os testes passam `gap=30` explicitamente e continuam valendo) e regenerar `python3 pipeline/quehorasvoto.py municipio pb 19313 --saida site/data`.

- [ ] **Passo 5 (pai): commit** `git add specs pipeline site/data && git commit -m "docs: calibração dos limites de fila"`

---

### Tarefa 5: licença, README e CI

**Executor:** Sol.

**Arquivos:**
- Criar: `LICENSE`, `README.md`, `.github/workflows/ci.yml`

**Interfaces:**
- Consome: CLI `secao` (Tarefa 2), testes do pipeline.
- Produz: job `testes` no CI. A Tarefa 6 acrescenta um passo a ele.

- [ ] **Passo 1: `LICENSE`**

```
MIT License

Copyright (c) 2026 dv-dev1

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Passo 2: rodar o comando real** e guardar a saída:

```bash
python3 pipeline/quehorasvoto.py secao --pleito 3220 pb 19313 0014 0001
```

- [ ] **Passo 3: `README.md`** (colar a saída do Passo 2 literalmente no bloco indicado)

````markdown
# quehorasvoto

Mostra quantas pessoas votaram em cada meia hora na sua seção eleitoral, a partir dos logs de urna publicados pelo TSE.
Serve para escolher o horário mais vazio no 2º turno de 25/10/2026.

```
$ python3 pipeline/quehorasvoto.py secao --pleito 3220 pb 19313 0014 0001
<saída real do Passo 2>
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
````

- [ ] **Passo 4: `.github/workflows/ci.yml`**

```yaml
name: ci
on: [push, pull_request]
jobs:
  testes:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.11", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: pipx run ruff check pipeline
      - run: python -m unittest discover -s pipeline
      - name: pipeline só usa stdlib (promessa do README)
        run: |
          python - <<'EOF'
          import ast, sys
          arvore = ast.parse(open("pipeline/quehorasvoto.py", encoding="utf-8").read())
          nomes = {a.name.split(".")[0] for n in ast.walk(arvore) if isinstance(n, ast.Import) for a in n.names}
          nomes |= {n.module.split(".")[0] for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom) and n.module}
          fora = nomes - set(sys.stdlib_module_names)
          sys.exit(f"fora da stdlib: {fora}" if fora else 0)
          EOF
```

- [ ] **Passo 5: rodar o que dá localmente**

Run: `pipx run ruff check pipeline || python3 -m ruff check pipeline` (se nenhum dos dois existir, registrar no relatório e deixar para o CI); `python3 -m unittest discover -s pipeline`; e o script de stdlib do Passo 4 colado no terminal.
Esperado: `All checks passed!`, `OK`, saída vazia com código 0. Prova do vermelho do script: acrescentar `import requests` temporário no topo do pipeline, rodar, ver `fora da stdlib: {'requests'}`, desfazer.

- [ ] **Passo 6 (pai): commit e push**, conferir o CI verde com `gh run watch`.

---

### Tarefa 6: lógica pura do frontend

**Executor:** Sol.

**Arquivos:**
- Criar: `site/calc.mjs`
- Criar: `test/calc.test.mjs`
- Modificar: `.github/workflows/ci.yml` (passo do node)

**Interfaces:**
- Consome: esquema do JSON (Tarefa 3); limites da seção `## Calibração` da spec (Tarefa 4). Se a calibração mudou 25/50, usar os valores novos no código **e** nos testes de borda de `nivel`.
- Produz (todos exportados de `site/calc.mjs`):
  - `LIMITES = { movimentado: 25, fila: 50 }`
  - `pct(fila: number, eleitores: number) -> number` (inteiro; 0 se `eleitores == 0`)
  - `nivel(p: number) -> 'tranquilo' | 'movimentado' | 'fila'`
  - `horaDoBloco(inicio: string, i: number) -> 'HH:MM'`
  - `faixa(hora: string) -> 'HH:MM–HH:MM'`
  - `serie(d: {inicio, eleitores, fila} | null | undefined) -> Array<{hora, eleitores, fila, pct, nivel}>`
  - `linhaDoTempo(...series) -> string[]` (horas únicas, ordenadas)
  - `melhorBloco(s) -> bloco | null` (menor `pct` entre blocos com eleitores; empate: menos eleitores; depois o mais cedo)
  - `lerHash(hash: string) -> {uf?, mun?, zona?, secao?}` (para na primeira parte inválida)
  - `montarHash(sel) -> string`
  - `posicaoNoRanking(ranking, chave, zona?) -> {pos, total} | null`

- [ ] **Passo 1: escrever os testes** em `test/calc.test.mjs`

```js
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
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `node --test test/calc.test.mjs`
Esperado: falha com `Cannot find module '.../site/calc.mjs'`.

- [ ] **Passo 3: implementar `site/calc.mjs`**

```js
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
```

- [ ] **Passo 4: rodar e ver passar**

Run: `node --test test/calc.test.mjs`
Esperado: `# pass 9`, `# fail 0`.

- [ ] **Passo 5: prova do vermelho.** Trocar `p <= LIMITES.fila` por `p < LIMITES.fila`: `nivel nas bordas` falha. Desfazer.

- [ ] **Passo 6: CI.** Acrescentar ao fim de `steps` em `.github/workflows/ci.yml`:

```yaml
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: node --test test/calc.test.mjs
```

- [ ] **Passo 7 (pai): commit** `git add site/calc.mjs test .github && git commit -m "feat: lógica pura do frontend"`

---

### Tarefa 7: site e Worker

**Executor:** Sol. O `npx wrangler dev` do aceite #4 fica com o pai se o sandbox barrar download pelo `npx`.

**Arquivos:**
- Criar: `site/index.html`, `site/app.js`, `site/style.css`, `wrangler.jsonc`

**Interfaces:**
- Consome: tudo de `site/calc.mjs` (Tarefa 6); `site/data/pb/index.json` e `site/data/pb/19313.json` (Tarefa 3).
- Produz: página em `/` que lê `#uf/mun/zona/secao`.

- [ ] **Passo 1: confirmar o link do TSE.** Abrir `https://www.tse.jus.br/servicos-eleitorais/autoatendimento-eleitoral#/atendimento-eleitor/onde-votar` no navegador. Se cair em "Onde votar", usar essa URL; se não, usar a URL que o menu "Onde votar" do autoatendimento mostrar.

- [ ] **Passo 2: `wrangler.jsonc`**

```jsonc
{
  "name": "quehorasvoto",
  "compatibility_date": "2026-10-01",
  // Só assets: os dados já vêm prontos do pipeline, o Worker não fala com o TSE.
  "assets": { "directory": "./site" }
}
```

- [ ] **Passo 3: `site/index.html`**

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Que horas voto?</title>
  <meta name="description" content="Veja quantas pessoas votaram em cada meia hora na sua seção e escolha o horário mais vazio para o 2º turno.">
  <meta name="theme-color" content="#0d0f12">
  <link rel="stylesheet" href="style.css">
  <script type="module" src="app.js"></script>
</head>
<body>
  <main id="app"><p class="carregando">Carregando…</p></main>
</body>
</html>
```

- [ ] **Passo 4: `site/app.js`**

```js
import { html, render, useState, useEffect } from 'https://cdn.jsdelivr.net/npm/htm@3.1.1/preact/standalone.module.js';
import { serie, melhorBloco, linhaDoTempo, lerHash, montarHash, posicaoNoRanking, faixa, pct } from './calc.mjs';

const UFS = [
  ['ac', 'Acre'], ['al', 'Alagoas'], ['ap', 'Amapá'], ['am', 'Amazonas'], ['ba', 'Bahia'], ['ce', 'Ceará'],
  ['df', 'Distrito Federal'], ['es', 'Espírito Santo'], ['go', 'Goiás'], ['ma', 'Maranhão'], ['mt', 'Mato Grosso'],
  ['ms', 'Mato Grosso do Sul'], ['mg', 'Minas Gerais'], ['pa', 'Pará'], ['pb', 'Paraíba'], ['pr', 'Paraná'],
  ['pe', 'Pernambuco'], ['pi', 'Piauí'], ['rj', 'Rio de Janeiro'], ['rn', 'Rio Grande do Norte'],
  ['rs', 'Rio Grande do Sul'], ['ro', 'Rondônia'], ['rr', 'Roraima'], ['sc', 'Santa Catarina'], ['sp', 'São Paulo'],
  ['se', 'Sergipe'], ['to', 'Tocantins'],
];
const ONDE_VOTAR = 'https://www.tse.jus.br/servicos-eleitorais/autoatendimento-eleitoral#/atendimento-eleitor/onde-votar';
const ROTULO = { tranquilo: 'Tranquilo', movimentado: 'Movimentado', fila: 'Fila' };
const TURNO24 = { 452: '2024 · 1º turno', 453: '2024 · 2º turno' };
const CHAVE = 'qhv:ultima';

const lembrar = (h) => { try { localStorage.setItem(CHAVE, h); } catch { /* aba anônima */ } };
const lembrada = () => { try { return localStorage.getItem(CHAVE) || ''; } catch { return ''; } };

async function buscar(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

function Select({ rotulo, valor, opcoes, aoMudar, desligado }) {
  return html`<label class="campo"><span>${rotulo}</span>
    <select value=${valor || ''} disabled=${desligado} onChange=${(e) => aoMudar(e.target.value || undefined)}>
      <option value="">Escolha</option>
      ${opcoes.map(([v, t]) => html`<option value=${v}>${t}</option>`)}
    </select></label>`;
}

function Grafico({ s26, s24, rotulo24, melhor }) {
  const horas = linhaDoTempo(s26, s24);
  const max = Math.max(1, ...s26.map((b) => b.eleitores), ...s24.map((b) => b.eleitores));
  const por = (s) => Object.fromEntries(s.map((b) => [b.hora, b]));
  const a = por(s26), b = por(s24);
  const alt = (x) => `${(100 * x.eleitores) / max}%`;
  return html`
    <div class="grafico" role="img" aria-label=${`Eleitores por meia hora em 2026. Melhor horário: ${faixa(melhor.hora)}.`}>
      ${horas.map((h) => html`
        <div class=${`coluna ${melhor.hora === h ? 'melhor' : ''}`}>
          <div class="barras">
            ${b[h] && html`<div class="fantasma" style=${{ height: alt(b[h]) }}></div>`}
            ${a[h] && html`<div class=${`barra ${a[h].nivel}`} style=${{ height: alt(a[h]) }}></div>`}
          </div>
          <span class="hora">${h.endsWith(':00') ? `${h.slice(0, 2)}h` : ''}</span>
        </div>`)}
    </div>
    <p class="legenda"><span class="ponto tranquilo"></span>Tranquilo <span class="ponto movimentado"></span>Movimentado
      <span class="ponto fila"></span>Fila ${s24.length ? html`<span class="ponto fantasma"></span>${rotulo24}` : ''}</p>
    <details><summary>Ver tabela</summary>
      <table><thead><tr><th>Horário</th><th>Votaram em 2026</th><th>Pegaram fila</th><th>Nível</th></tr></thead>
        <tbody>${s26.map((x) => html`<tr><td>${faixa(x.hora)}</td><td>${x.eleitores}</td><td>${x.pct}%</td><td>${ROTULO[x.nivel]}</td></tr>`)}</tbody>
      </table></details>`;
}

function Secao({ mun, chave }) {
  const d = mun.secoes[chave];
  const turnos = ['453', '452'].filter((p) => d[p]);
  const [p24, setP24] = useState(turnos[0]);
  const s26 = serie(d['3220']);
  if (!s26.length) {
    return html`<section class="card vazio">Esta seção não tem log de urna em 2026 (urna substituída sem arquivo ou votação em cédula). Veja o ranking do município abaixo.</section>`;
  }
  const s24 = serie(d[p24]);
  const melhor = melhorBloco(s26);
  const total = s26.reduce((t, b) => t + b.eleitores, 0);
  const pico = s26.reduce((a, b) => (b.eleitores > a.eleitores ? b : a));
  const pos = posicaoNoRanking(mun.ranking, chave);
  return html`
    <section class="card destaque">
      <span class="rotulo">Melhor horário</span>
      <strong class="numero">${faixa(melhor.hora)}</strong>
      <span class=${`chip ${melhor.nivel}`}>${ROTULO[melhor.nivel]}</span>
      <p>No 1º turno, ${melhor.eleitores} ${melhor.eleitores === 1 ? 'pessoa votou' : 'pessoas votaram'} nesse bloco e ${melhor.pct}% pegaram fila.</p>
    </section>
    <div class="numeros">
      <div class="card"><span class="rotulo">Votaram em 2026</span><strong>${total}</strong></div>
      <div class="card"><span class="rotulo">Pegaram fila</span><strong>${pct(s26.reduce((t, b) => t + b.fila, 0), total)}%</strong></div>
      <div class="card"><span class="rotulo">Pico</span><strong>${faixa(pico.hora)}</strong></div>
      ${pos && html`<div class="card"><span class="rotulo">Fila no município</span><strong>${pos.pos}ª de ${pos.total}</strong></div>`}
    </div>
    <section class="card">
      <div class="titulo"><h2>Eleitores por meia hora</h2>
        ${turnos.length > 1 && html`<div class="alternar">${turnos.map((p) => html`
          <button aria-pressed=${p === p24} onClick=${() => setP24(p)}>${TURNO24[p]}</button>`)}</div>`}
      </div>
      <${Grafico} s26=${s26} s24=${s24} rotulo24=${TURNO24[p24]} melhor=${melhor} />
    </section>`;
}

function Ranking({ mun, zonas, chave }) {
  const [zona, setZona] = useState('');
  const lista = mun.ranking.filter(([k]) => !zona || k.startsWith(`${zona}/`)).slice(0, 10);
  return html`<section class="card">
    <div class="titulo"><h2>Seções com mais fila em ${mun.nm}</h2>
      <${Select} rotulo="Zona" valor=${zona} opcoes=${zonas.map((z) => [z, z])} aoMudar=${(z) => setZona(z || '')} />
    </div>
    <ol class="ranking">${lista.map(([k, p, n]) => html`
      <li class=${k === chave ? 'sua' : ''}><a href=${`#${mun.uf}/${mun.cd}/${k}`}>Zona ${k.split('/')[0]} · Seção ${k.split('/')[1]}</a>
        <span>${p}% fila · ${n} eleitores</span></li>`)}</ol>
    <p class="nota">Percentual de eleitores habilitados menos de 30 s depois do voto anterior, 1º turno de 2026.</p>
  </section>`;
}

function App() {
  const [sel, setSel] = useState(() => lerHash(location.hash || lembrada()));
  const [indice, setIndice] = useState(null);
  const [mun, setMun] = useState(null);
  const [erro, setErro] = useState('');

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
    setIndice(null); setErro('');
    if (sel.uf) buscar(`data/${sel.uf}/index.json`).then(setIndice, () => setErro('Os dados deste estado ainda não foram publicados.'));
  }, [sel.uf]);
  useEffect(() => {
    setMun(null);
    if (sel.uf && sel.mun) buscar(`data/${sel.uf}/${sel.mun}.json`).then(setMun, () => setErro('Os dados deste município ainda não foram publicados.'));
  }, [sel.uf, sel.mun]);

  const chaves = mun ? Object.keys(mun.secoes).filter((k) => '3220' in mun.secoes[k]) : [];
  const zonas = [...new Set(chaves.map((k) => k.split('/')[0]))];
  const secoes = chaves.filter((k) => k.startsWith(`${sel.zona}/`)).map((k) => k.split('/')[1]);
  const chave = sel.zona && sel.secao ? `${sel.zona}/${sel.secao}` : null;

  return html`
    <header><h1>Que horas voto?</h1>
      <p>Quantas pessoas votaram em cada meia hora na sua seção. Escolha o horário mais vazio para o 2º turno, em 25/10.</p></header>
    <section class="card seletor">
      <${Select} rotulo="Estado" valor=${sel.uf} opcoes=${UFS} aoMudar=${(uf) => setSel({ uf })} />
      <${Select} rotulo="Município" valor=${sel.mun} opcoes=${indice || []} desligado=${!indice} aoMudar=${(m) => setSel({ uf: sel.uf, mun: m })} />
      <${Select} rotulo="Zona" valor=${sel.zona} opcoes=${zonas.map((z) => [z, z])} desligado=${!mun} aoMudar=${(zona) => setSel({ uf: sel.uf, mun: sel.mun, zona })} />
      <${Select} rotulo="Seção" valor=${sel.secao} opcoes=${secoes.map((s) => [s, s])} desligado=${!sel.zona} aoMudar=${(secao) => setSel({ ...sel, secao })} />
      <a class="tse" href=${ONDE_VOTAR} target="_blank" rel="noopener">Não sabe sua zona e seção? Consulte no TSE</a>
    </section>
    ${erro && html`<p class="card aviso" role="status">${erro}</p>`}
    ${mun && chave && mun.secoes[chave] && html`<${Secao} key=${chave} mun=${mun} chave=${chave} />`}
    ${mun && html`<${Ranking} mun=${mun} zonas=${zonas} chave=${chave} />`}
    <footer>Dados: logs de urna do TSE (1º turno 2026, 1º e 2º turnos 2024). Hora local da urna.
      <a href="https://github.com/dv-dev1/quehorasvoto">Código aberto</a></footer>`;
}

render(html`<${App} />`, document.getElementById('app'));
```

- [ ] **Passo 5: `site/style.css`** (base funcional; o passe da Tarefa 11 refina)

```css
:root {
  color-scheme: dark;
  --fundo: #0d0f12; --card: #15181d; --borda: #252a33; --texto: #e8eaed; --fraco: #8b93a1;
  --tranquilo: #3ecf8e; --movimentado: #f5b941; --fila: #f2555a; --acento: #7aa2ff; --raio: 14px;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fundo); color: var(--texto); font: 16px/1.5 system-ui, sans-serif; }
#app { max-width: 880px; margin: 0 auto; padding: 24px 16px 48px; display: grid; gap: 16px; }
h1 { font-size: clamp(2rem, 6vw, 3rem); margin: 0; letter-spacing: -0.02em; }
h2 { font-size: 1rem; margin: 0; }
header p, .nota, .legenda, footer { color: var(--fraco); }
.card { background: var(--card); border: 1px solid var(--borda); border-radius: var(--raio); padding: 20px; margin: 0; }
.seletor { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.campo { display: grid; gap: 4px; font-size: 0.85rem; color: var(--fraco); }
select { background: var(--fundo); color: var(--texto); border: 1px solid var(--borda); border-radius: 10px; padding: 12px; font-size: 1rem; }
select:focus-visible, button:focus-visible, a:focus-visible { outline: 2px solid var(--acento); outline-offset: 2px; }
.tse, a { color: var(--acento); }
.tse { grid-column: 1 / -1; }
.destaque { display: grid; gap: 4px; }
.rotulo { font-size: 0.85rem; color: var(--fraco); }
.numero { font-size: clamp(2.5rem, 10vw, 4rem); line-height: 1.1; font-variant-numeric: tabular-nums; }
.chip { justify-self: start; padding: 2px 10px; border-radius: 99px; font-weight: 600; color: #0d0f12; }
.chip.tranquilo, .barra.tranquilo, .ponto.tranquilo { background: var(--tranquilo); }
.chip.movimentado, .barra.movimentado, .ponto.movimentado { background: var(--movimentado); }
.chip.fila, .barra.fila, .ponto.fila { background: var(--fila); }
.numeros { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.numeros strong { display: block; font-size: 1.5rem; font-variant-numeric: tabular-nums; }
.titulo { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 16px; }
.alternar button { background: none; color: var(--fraco); border: 1px solid var(--borda); border-radius: 99px; padding: 6px 12px; cursor: pointer; }
.alternar button[aria-pressed="true"] { color: var(--texto); border-color: var(--acento); }
.grafico { display: flex; align-items: flex-end; gap: 3px; height: 200px; }
.coluna { flex: 1; display: grid; grid-template-rows: 1fr auto; height: 100%; min-width: 0; }
.barras { position: relative; }
.barras > div { position: absolute; bottom: 0; left: 0; right: 0; border-radius: 4px 4px 0 0; }
.fantasma, .ponto.fantasma { background: rgba(232, 234, 237, 0.12); }
.barra { left: 20% !important; right: 20% !important; }
.coluna.melhor .barra { box-shadow: 0 0 0 2px var(--texto); }
.hora { font-size: 0.7rem; color: var(--fraco); text-align: center; height: 1.2em; }
.ponto { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin: 0 4px 0 12px; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-variant-numeric: tabular-nums; }
td, th { text-align: left; padding: 6px 4px; border-bottom: 1px solid var(--borda); }
.ranking { margin: 0; padding-left: 1.5em; display: grid; gap: 8px; }
.ranking li span { display: block; font-size: 0.85rem; color: var(--fraco); }
.ranking li.sua a { font-weight: 700; }
.aviso, .vazio { color: var(--movimentado); }
```

- [ ] **Passo 6: checagem local sem wrangler**

```bash
python3 -m http.server 8788 -d site >/dev/null 2>&1 & sleep 1
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8788/ http://localhost:8788/app.js http://localhost:8788/calc.mjs http://localhost:8788/data/pb/19313.json http://localhost:8788/data/pb/index.json
kill %1
node --test test/calc.test.mjs
```
Esperado: `200` cinco vezes; testes JS passando.

- [ ] **Passo 7 (pai): critério de aceite #4** e verificação no navegador

```bash
npx wrangler dev & sleep 5; curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8787/ http://localhost:8787/data/pb/19313.json
```
Esperado: `200` duas vezes. Abrir `http://localhost:8787/#pb/19313/0014/0001` (cmux ou Playwright): aparecem o melhor horário, o gráfico com barras e o ranking de Bananeiras; o console não tem erro; mudar a seção atualiza o hash; recarregar sem hash volta à última seção.

- [ ] **Passo 8 (pai): commit** `git add site wrangler.jsonc && git commit -m "feat: site estático e Worker"`

---

### Tarefa 8 (pai): deploy do recorte vertical

**Executor:** agente pai. Faixa vermelha (publica na internet).

- [ ] **Passo 1:** `npx wrangler login` (o usuário autoriza no navegador, se ainda não estiver logado).
- [ ] **Passo 2: critério de aceite #6 (recorte):** `npx wrangler deploy`. Esperado: URL `https://quehorasvoto.<conta>.workers.dev`.
- [ ] **Passo 3:** abrir `<url>/#pb/19313/0014/0001` no navegador e no celular (largura 375 px): gráfico, melhor horário e ranking de Bananeiras aparecem.
- [ ] **Passo 4:** `git push`.

---

### Tarefa 9: coleta de uma UF inteira com retomada

**Executor:** Sol.

**Arquivos:**
- Modificar: `pipeline/quehorasvoto.py`
- Modificar: `pipeline/test_quehorasvoto.py`

**Interfaces:**
- Consome: `carregar_cs`, `montar_municipio`, `indice`, `escrever_json`, `_municipios` (Tarefa 3).
- Produz:
  - `rodar_uf(uf, saida: Path, baixar=baixar, paralelo=8, ate: float | None = None) -> int`: grava o índice; para cada município do 3220 cujo JSON ainda não existe, monta e grava; erro num município vai para o stderr e não para os outros; não começa município novo depois de `ate` segundos; imprime `"<uf>: feitos X, pulados Y, falhas Z, faltam W"`; devolve 0 se `faltam == 0`, senão 1
  - subcomando `uf <uf> [--saida site/data] [--paralelo 8] [--ate SEGUNDOS]`

- [ ] **Passo 1: escrever os testes**

```python
CONFIGS_UF = {
    "3220": cs(("19313", "BANANEIRAS", {"0001": ["0001", "0002"]}), ("20000", "QUEBRADO", {"0001": ["0001"]})),
    "452": cs(("19313", "BANANEIRAS", {"0001": ["0001", "0003"]})),
    "453": {},
}


def mapa_uf(quebrado):
    m = {q.url_cs(p, "pb"): json.dumps(c).encode() for p, c in CONFIGS_UF.items() if c}
    m.update(mapa_bananeiras())
    m[q.url_aux("3220", "pb", "20000", "0001", "0001")] = quebrado
    return m


class TestUf(unittest.TestCase):
    def test_falha_isolada_e_retomada(self):
        with tempfile.TemporaryDirectory() as d:
            saida = Path(d)
            rede = urllib.error.URLError("503")
            self.assertEqual(q.rodar_uf("pb", saida, baixar=fake_baixar(mapa_uf(rede)), paralelo=2), 1)
            feito = saida / "pb" / "19313.json"
            self.assertTrue(feito.exists())
            self.assertFalse((saida / "pb" / "20000.json").exists())
            self.assertEqual(json.loads((saida / "pb" / "index.json").read_text(encoding="utf-8"))[0][1], "BANANEIRAS")
            antes = feito.read_bytes()

            segunda = mapa_uf(aux("h"))
            for url in mapa_bananeiras():
                del segunda[url]
            self.assertEqual(q.rodar_uf("pb", saida, baixar=fake_baixar(segunda), paralelo=2), 0)
            self.assertEqual(feito.read_bytes(), antes)
            self.assertEqual(json.loads((saida / "pb" / "20000.json").read_text(encoding="utf-8"))["secoes"], {"0001/0001": {"3220": None}})

    def test_prazo_esgotado_nao_comeca_municipio(self):
        with tempfile.TemporaryDirectory() as d:
            saida = Path(d)
            self.assertEqual(q.rodar_uf("pb", saida, baixar=fake_baixar(mapa_uf(aux("h"))), ate=0), 1)
            self.assertEqual(sorted(p.name for p in (saida / "pb").iterdir()), ["index.json"])
```

No segundo `rodar_uf`, a seção `20000` tem aux mas não tem o log mapeado, então vira `None`; e as URLs de Bananeiras foram removidas, então se ela fosse reprocessada o arquivo mudaria.

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `AttributeError: module 'quehorasvoto' has no attribute 'rodar_uf'`.

- [ ] **Passo 3: implementar**

```python
def rodar_uf(uf, saida, baixar=baixar, paralelo=8, ate=None):
    # Retomável: o JSON gravado é o checkpoint, e a próxima rodada da Action pula o que já existe.
    configs = {p: carregar_cs(p, uf, baixar) for p in PLEITOS}
    destino = Path(saida) / uf
    escrever_json(destino / "index.json", indice(configs["3220"]))
    muns = [m["cd"] for m in _municipios(configs["3220"])]
    inicio, feitos, pulados, falhas = time.monotonic(), 0, 0, 0
    for mun in muns:
        arquivo = destino / f"{mun}.json"
        if arquivo.exists():
            pulados += 1
            continue
        if ate is not None and time.monotonic() - inicio >= ate:
            break
        try:
            escrever_json(arquivo, montar_municipio(uf, mun, configs, baixar=baixar, paralelo=paralelo))
            feitos += 1
        except Exception as e:  # um município ruim não pode derrubar a UF inteira
            falhas += 1
            print(f"falha {uf}/{mun}: {e!r}", file=sys.stderr)
    faltam = sum(not (destino / f"{m}.json").exists() for m in muns)
    print(f"{uf}: feitos {feitos}, pulados {pulados}, falhas {falhas}, faltam {faltam}")
    return 0 if faltam == 0 else 1
```

No `main`:

```python
    u = sub.add_parser("uf", help="todos os municípios de uma UF, retomável")
    u.add_argument("uf")
    u.add_argument("--saida", default="site/data")
    u.add_argument("--paralelo", type=int, default=8)
    u.add_argument("--ate", type=float, help="não começa município novo depois de N segundos")
```

```python
    if a.cmd == "uf":
        return rodar_uf(a.uf.lower(), a.saida, paralelo=a.paralelo, ate=a.ate)
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m unittest discover -s pipeline`
Esperado: `OK`.

- [ ] **Passo 5: prova do vermelho.** Comentar o `continue` de `if arquivo.exists()`: `test_falha_isolada_e_retomada` falha. Desfazer.

- [ ] **Passo 6: rodada real numa UF pequena**

Run: `time python3 pipeline/quehorasvoto.py uf rr --saida site/data`
Esperado: termina com `rr: feitos 15, pulados 0, falhas 0, faltam 0` (Roraima tem 15 municípios) e código 0. Colar o tempo no relatório: ele dá a velocidade (seções/s) para estimar SP e MG.

- [ ] **Passo 7 (pai): commit** `git add pipeline site/data/rr && git commit -m "feat: coleta retomável por UF"`

---

### Tarefa 10: Action de coleta nacional

**Executor:** Sol.

**Arquivos:**
- Criar: `.github/workflows/dados.yml`

**Interfaces:**
- Consome: subcomando `uf` (Tarefa 9).
- Produz: commit de `site/data/<uf>/` na `main` a cada rodada.

- [ ] **Passo 1: escrever a checagem** (falha enquanto o arquivo não existe)

```bash
python3 - <<'EOF'
import re
t = open(".github/workflows/dados.yml", encoding="utf-8").read()
ufs = re.search(r"uf: \[([^\]]+)\]", t).group(1).replace(" ", "").split(",")
print("workflow_dispatch" in t, len(ufs), len(set(ufs)), "--ate" in t, "max-parallel" in t)
EOF
```
Esperado agora: `FileNotFoundError`.

- [ ] **Passo 2: escrever o workflow**

```yaml
name: dados
on:
  workflow_dispatch:
permissions:
  contents: write
concurrency: dados
jobs:
  coletar:
    runs-on: ubuntu-latest
    timeout-minutes: 350
    strategy:
      fail-fast: false
      # Limita o paralelismo total contra o CDN do TSE: 8 jobs x 8 threads.
      max-parallel: 8
      matrix:
        uf: [ac, al, am, ap, ba, ce, df, es, go, ma, mg, ms, mt, pa, pb, pe, pi, pr, rj, rn, ro, rr, rs, sc, se, sp, to]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      # --ate para antes do timeout do job, com folga para um município grande já começado terminar.
      - run: python pipeline/quehorasvoto.py uf ${{ matrix.uf }} --saida site/data --paralelo 8 --ate 16200
      - if: always()
        uses: actions/upload-artifact@v4
        with:
          name: dados-${{ matrix.uf }}
          path: site/data/${{ matrix.uf }}
          if-no-files-found: ignore
          retention-days: 3
  publicar:
    needs: coletar
    if: always()
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          pattern: dados-*
          path: baixado
      - run: |
          for d in baixado/dados-*; do
            uf="${d#baixado/dados-}"
            mkdir -p "site/data/$uf"
            cp -r "$d/." "site/data/$uf/"
          done
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add site/data
          git diff --cached --quiet || git commit -m "dados: coleta $(date -u +%F)"
          git pull --rebase
          git push
```

- [ ] **Passo 3: rodar a checagem do Passo 1**
Esperado: `True 27 27 True True`.

- [ ] **Passo 4 (pai): commit e push** `git add .github/workflows/dados.yml && git commit -m "ci: coleta nacional por UF" && git push`

---

### Tarefa 11 (pai): passe de UI com `impeccable`

**Executor:** agente pai (Claude), com a skill `impeccable`. Não vai para o Sol: a skill é do Claude.

**Arquivos:**
- Modificar: `site/style.css`, `site/app.js`, `site/index.html`
- Não tocar: `site/calc.mjs`, o esquema do JSON, o hash `#uf/mun/zona/secao`.

- [ ] **Passo 1:** invocar `Skill` `impeccable` com este pedido: "Polir a UI de `site/` (Preact + htm sem build, tema escuro). Referência de usabilidade: seuimposto.com (número grande em destaque, cards limpos, selects grandes); não copiar marca, cores, fontes nem assets dele. Prioridades: o melhor horário legível em 1 segundo no celular de 375 px; nível de fila nunca só por cor (o texto do chip fica); contraste AA; foco visível; gráfico legível com 2024 apagado atrás; estado vazio e de erro com texto útil. Não mudar `calc.mjs`, o esquema do JSON nem o formato do hash."
- [ ] **Passo 2:** `node --test test/calc.test.mjs` continua passando.
- [ ] **Passo 3:** com `npx wrangler dev`, capturas em 375 px e 1280 px de `#pb/19313/0014/0001`, de uma seção sem dado (se Bananeiras não tiver, editar uma cópia local do JSON só para a captura, sem commitar) e do estado inicial sem hash. Mostrar ao usuário.
- [ ] **Passo 4:** commit `git commit -am "style: passe de UI"` e `npx wrangler deploy`.

---

### Tarefa 12 (pai): coleta nacional e deploy final

**Executor:** agente pai. Faixa vermelha (dispara a Action e publica).

- [ ] **Passo 1:** `gh workflow run dados.yml` e acompanhar com `gh run watch`. Cada job imprime `"<uf>: feitos X, pulados Y, falhas Z, faltam W"`.
- [ ] **Passo 2:** enquanto algum job terminar com `faltam > 0`, rodar de novo (`gh workflow run dados.yml`). A rodada seguinte pula o que já está commitado.
- [ ] **Passo 3:** `git pull` e conferir os limites do Workers Free:

```bash
find site -type f | wc -l
find site/data -type f -size +20M
du -sh site/data
python3 - <<'EOF'
import json, pathlib
for uf in sorted(p.name for p in pathlib.Path("site/data").iterdir()):
    idx = json.load(open(f"site/data/{uf}/index.json", encoding="utf-8"))
    falta = [cd for cd, _ in idx if not pathlib.Path(f"site/data/{uf}/{cd}.json").exists()]
    print(uf, len(idx), "faltam", len(falta))
EOF
```
Esperado: menos de 20.000 arquivos; nenhum arquivo acima de 20 MB; 27 UFs com `faltam 0`. Se algum município passar de 20 MB, parar e decidir com o usuário (ver Questões abertas).

- [ ] **Passo 4:** rodar os critérios de aceite #1 a #5 e colar as saídas.
- [ ] **Passo 5: aceite #6:** `npx wrangler deploy`; abrir `#pb/19313/0014/0001`, uma seção da capital de SP (`#sp/71072/...`) e uma do Acre (votação de 06h a 15h, hora local).

---

## Questões abertas

- **Tamanho do JSON da capital de SP**: a estimativa é de ~12 MB sem compressão (perto de 2 MB com brotli). Cabe no limite de 25 MiB, mas é pesado no 4G. Se a medida real na Tarefa 12 passar de 20 MB, ou o carregamento no celular ficar ruim, dividir por zona só os municípios grandes, o que muda o esquema. Não está planejado agora.
- **Tempo da coleta de SP e MG**: a Tarefa 9 mede a velocidade em RR. Se SP não couber em 5 h, a retomada do Passo 2 da Tarefa 12 resolve com 2 ou 3 rodadas, sem mudar o código.
- **Série de 2024 no gráfico**: o padrão é mostrar o 2º turno de 2024 quando existe (mais parecido com o 2º turno de 2026) e o 1º turno nos outros casos, com botão para alternar. A spec não fixa isso.
