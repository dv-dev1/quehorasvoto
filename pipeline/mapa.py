"""Contornos do IBGE e percentual de fila do primeiro turno de 2026."""

import argparse
import gzip
import json
import math
import re
import sys
import unicodedata
from itertools import pairwise
from pathlib import Path

import quehorasvoto as q

LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas"
PARAMETROS = "?formato=application/vnd.geo%2Bjson&intrarregiao="
ALIASES = {
    ("go", "92690"): 5203500,
    ("mg", "41092"): 3105509,
    ("mg", "44571"): 3122900,
    ("mg", "53031"): 3165206,
    ("mt", "91553"): 5107800,
    ("pa", "04120"): 1502954,
    ("pr", "77119"): 4116307,
    ("rn", "17035"): 2405306,
    ("ro", "00337"): 1100346,
    ("ro", "00256"): 1100098,
    ("rr", "03158"): 1400605,
    ("se", "31011"): 2800100,
    ("sp", "71013"): 3550001,
}
# Criado em 2023 (desmembrado de Sorriso): a malha do IBGE ainda não tem o contorno.
SEM_MALHA = {("mt", "73709")}


def normalizar(nome):
    ascii_nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub("[^a-z]", "", ascii_nome.lower())


def codigo_ibge(uf, cd, nome, nomes):
    return ALIASES.get((uf, cd), nomes.get((uf, normalizar(nome))))


def aneis(geometria):
    if geometria["type"] == "Polygon":
        return geometria["coordinates"]
    if geometria["type"] == "MultiPolygon":
        return [anel for poligono in geometria["coordinates"] for anel in poligono]
    raise ValueError(f"geometria não suportada: {geometria['type']}")


def projecao(feicoes):
    pontos = [p for f in feicoes for anel in aneis(f["geometry"]) for p in anel]
    lon_min = min(p[0] for p in pontos)
    lon_max = max(p[0] for p in pontos)
    lat_min = min(p[1] for p in pontos)
    lat_max = max(p[1] for p in pontos)
    cosseno = math.cos(math.radians((lat_min + lat_max) / 2))
    escala = 1000 / ((lon_max - lon_min) * cosseno)

    def projetar(p):
        return round((p[0] - lon_min) * cosseno * escala), round((lat_max - p[1]) * escala)

    return projetar, round((lat_max - lat_min) * escala)


def pontos_anel(anel, projetar):
    pontos = []
    for ponto in anel:
        p = projetar(ponto)
        if not pontos or p != pontos[-1]:
            pontos.append(p)
    if len(pontos) > 1 and pontos[0] == pontos[-1]:
        pontos.pop()
    return pontos if len(set(pontos)) >= 3 else []


def caminho(geometria, projetar):
    partes = []
    for anel in aneis(geometria):
        pontos = pontos_anel(anel, projetar)
        if not pontos:
            continue
        partes.append(f"M{pontos[0][0]} {pontos[0][1]}")
        for (x, y), (nx, ny) in pairwise(pontos):
            partes.append(f"l{nx - x} {ny - y}")
        partes.append("z")
    return "".join(partes)


def rotulo(geometria, projetar):
    maior, centro = 0, (0, 0)
    for anel in aneis(geometria):
        pontos = pontos_anel(anel, projetar)
        area, soma_x, soma_y = 0, 0, 0
        for (x, y), (nx, ny) in zip(pontos, pontos[1:] + pontos[:1]):
            cruzado = x * ny - nx * y
            area += cruzado
            soma_x += (x + nx) * cruzado
            soma_y += (y + ny) * cruzado
        if abs(area) > maior:
            maior = abs(area)
            centro = round(soma_x / (3 * area)), round(soma_y / (3 * area))
    return centro


def totais_fila(arquivo):
    if not arquivo.exists():
        return 0, 0
    municipio = json.loads(arquivo.read_text(encoding="utf-8"))
    fila, eleitores = 0, 0
    for pleitos in municipio["secoes"].values():
        dados = pleitos.get("3220")
        if dados:
            fila += sum(dados["fila"])
            eleitores += sum(dados["eleitores"])
    return fila, eleitores


def percentual(fila, eleitores):
    return round(100 * fila / eleitores, 1) if eleitores else None


def baixar_json(url, baixar):
    dados = baixar(url)
    if dados is None:
        raise ValueError(f"IBGE sem dados: {url}")
    if dados.startswith(b"\x1f\x8b"):
        dados = gzip.decompress(dados)
    return json.loads(dados)


def rodar(saida, baixar=q.baixar):
    saida = Path(saida)
    localidades = baixar_json(LOCALIDADES, baixar)
    nomes = {(m["UF-sigla"].lower(), normalizar(m["municipio-nome"])): m["municipio-id"] for m in localidades}
    ufs = {m["UF-sigla"].lower(): str(m["UF-id"]) for m in localidades}
    brasil = baixar_json(f"{MALHA}/paises/BR{PARAMETROS}UF&qualidade=minima", baixar)["features"]
    projetar_br, altura_br = projecao(brasil)
    contornos_br = {f["properties"]["codarea"]: f["geometry"] for f in brasil}
    mapa_br = {"w": 1000, "h": altura_br, "ufs": {}}
    municipios, faltantes = 0, []
    for uf, codigo_uf in sorted(ufs.items()):
        indice = json.loads((saida / uf / "index.json").read_text(encoding="utf-8"))
        feicoes = baixar_json(
            f"{MALHA}/estados/{uf.upper()}{PARAMETROS}municipio&qualidade=minima", baixar,
        )["features"]
        projetar, altura = projecao(feicoes)
        contornos = {f["properties"]["codarea"]: f["geometry"] for f in feicoes}
        mapa_uf = {"w": 1000, "h": altura, "muns": {}}
        fila_uf, eleitores_uf = 0, 0
        for cd, nome in indice:
            municipios += 1
            fila, eleitores = totais_fila(saida / uf / f"{cd}.json")
            fila_uf += fila
            eleitores_uf += eleitores
            geometria = contornos.get(str(codigo_ibge(uf, cd, nome, nomes)))
            d = caminho(geometria, projetar) if geometria else ""
            if not d:
                if (uf, cd) in SEM_MALHA:
                    continue
                faltantes.append(f"{uf}/{cd} {nome}")
                continue
            mapa_uf["muns"][cd] = {"d": d, "pct": percentual(fila, eleitores)}
        geometria_uf = contornos_br[codigo_uf]
        x, y = rotulo(geometria_uf, projetar_br)
        mapa_br["ufs"][uf] = {
            "d": caminho(geometria_uf, projetar_br), "pct": percentual(fila_uf, eleitores_uf), "x": x, "y": y,
        }
        q.escrever_json(saida / "mapa" / f"{uf}.json", mapa_uf)
    q.escrever_json(saida / "mapa" / "br.json", mapa_br)
    for faltante in faltantes:
        print(f"sem contorno: {faltante}", file=sys.stderr)
    print(f"{len(ufs)} UFs, {municipios} municípios, {len(faltantes)} sem contorno")
    return 1 if faltantes else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mapa")
    ap.add_argument("--saida", default="site/data")
    a = ap.parse_args(argv)
    return rodar(a.saida, baixar=q.baixar)


if __name__ == "__main__":
    sys.exit(main())
