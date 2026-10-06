"""Quantas pessoas votaram em cada meia hora de cada seção, a partir dos logs de urna do TSE."""

import argparse
import http.client
import io
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead, OSError) as e:
            erro = e
        if n < tentativas - 1:
            time.sleep(espera * 2**n)
    raise erro


def ler_jez(dados):
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            return z.read("logd.dat").decode("latin1")
    except (zipfile.BadZipFile, KeyError, zlib.error, EOFError):
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


def rodar_uf(uf, saida, baixar=baixar, paralelo=8, ate=None):
    # Retomável: o JSON gravado é o checkpoint, e a próxima rodada da Action pula o que já existe.
    configs = {p: carregar_cs(p, uf, baixar) for p in PLEITOS}
    if not _municipios(configs["3220"]):
        print(f"falha {uf}: configuração 3220 ausente ou sem municípios", file=sys.stderr)
        return 1
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
        except Exception as e:  # noqa: BLE001 — um município ruim não pode derrubar a UF inteira
            falhas += 1
            print(f"falha {uf}/{mun}: {e!r}", file=sys.stderr)
    faltam = sum(not (destino / f"{m}.json").exists() for m in muns)
    print(f"{uf}: feitos {feitos}, pulados {pulados}, falhas {falhas}, faltam {faltam}")
    return 0 if faltam == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="quehorasvoto")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("secao", help="blocos de meia hora de uma seção")
    s.add_argument("--pleito", choices=list(PLEITOS), default="3220")
    for nome in ("uf", "mun", "zona", "secao"):
        s.add_argument(nome)
    m = sub.add_parser("municipio", help="JSON de um município")
    m.add_argument("uf")
    m.add_argument("mun")
    m.add_argument("--saida", default="site/data")
    m.add_argument("--paralelo", type=int, default=8)
    u = sub.add_parser("uf", help="todos os municípios de uma UF, retomável")
    u.add_argument("uf")
    u.add_argument("--saida", default="site/data")
    u.add_argument("--paralelo", type=int, default=8)
    u.add_argument("--ate", type=float, help="não começa município novo depois de N segundos")
    a = ap.parse_args(argv)
    if a.cmd == "secao":
        print(json.dumps(processar_secao(a.pleito, a.uf.lower(), a.mun, a.zona, a.secao)))
    if a.cmd == "municipio":
        uf = a.uf.lower()
        configs = {p: carregar_cs(p, uf) for p in PLEITOS}
        destino = Path(a.saida) / uf
        escrever_json(destino / f"{a.mun}.json", montar_municipio(uf, a.mun, configs, paralelo=a.paralelo))
        escrever_json(destino / "index.json", indice(configs["3220"]))
        print(destino / f"{a.mun}.json")
    if a.cmd == "uf":
        return rodar_uf(a.uf.lower(), a.saida, paralelo=a.paralelo, ate=a.ate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
