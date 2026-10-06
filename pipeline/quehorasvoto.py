"""Quantas pessoas votaram em cada meia hora de cada seção, a partir dos logs de urna do TSE."""

import argparse
import http.client
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
import zlib

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
