import gzip
import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import mapa as m
import quehorasvoto as q

LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas"
PARAMETROS = "?formato=application/vnd.geo%2Bjson&intrarregiao="
BRASIL = MALHA + "/paises/BR" + PARAMETROS + "UF&qualidade=minima"
ESTADO = MALHA + "/estados/PB" + PARAMETROS + "municipio&qualidade=minima"


def feicao(codigo, aneis, tipo="Polygon"):
    return {"type": "Feature", "properties": {"codarea": str(codigo)},
            "geometry": {"type": tipo, "coordinates": aneis}}


def colecao(*feicoes):
    return {"type": "FeatureCollection", "features": list(feicoes)}


def dados_municipio(eleitores, fila):
    return {"secoes": {
        "0001/0001": {"3220": {"eleitores": eleitores, "fila": fila},
                      "452": {"eleitores": [1000], "fila": [1000]}},
        "0001/0002": {"3220": {"eleitores": [10], "fila": [2]}},
        "0001/0003": {"3220": None},
        "0001/0004": {"453": None},
    }}


class TestMapa(unittest.TestCase):
    def test_normalizacao_alias_e_grafia_diferente(self):
        self.assertEqual(m.normalizar(" ÁGUA-Branca 123 "), "aguabranca")
        nomes = {("rn", "januariocicco"): 2405306, ("mg", "saotomedasletras"): 3165206,
                 ("pb", "januariocicco"): 999}
        self.assertEqual(m.codigo_ibge("rn", "17035", "BOA SAÚDE", nomes), 2405306)
        self.assertIsNone(m.codigo_ibge("mg", "99999", "SÃO THOMÉ DAS LETRAS", nomes))
        self.assertEqual(m.codigo_ibge("mg", "53031", "SÃO THOMÉ DAS LETRAS", nomes), 3165206)
        self.assertEqual(m.codigo_ibge("pb", "00001", "Januário Cicco", nomes), 999)
        aliases = {
            ("go", "92690"): 5203500, ("mg", "41092"): 3105509, ("mg", "44571"): 3122900,
            ("mg", "53031"): 3165206, ("mt", "91553"): 5107800, ("pa", "04120"): 1502954,
            ("pr", "77119"): 4116307, ("rn", "17035"): 2405306, ("ro", "00337"): 1100346,
            ("ro", "00256"): 1100098, ("rr", "03158"): 1400605, ("se", "31011"): 2800100,
            ("sp", "71013"): 3550001,
        }
        for (uf, cd), esperado in aliases.items():
            with self.subTest(uf=uf, cd=cd):
                self.assertEqual(m.codigo_ibge(uf, cd, "nome ignorado", {}), esperado)

    def test_projecao_quadrado_e_latitude_media(self):
        for latitude in (0, 59):
            with self.subTest(latitude=latitude):
                anel = [[0, latitude], [2, latitude], [2, latitude + 2], [0, latitude + 2], [0, latitude]]
                projetar, altura = m.projecao([feicao(1, [anel])])
                self.assertEqual(altura, round(1000 / math.cos(math.radians(latitude + 1))))
                self.assertEqual(projetar([0, latitude + 2]), (0, 0))
                self.assertEqual(projetar([2, latitude]), (1000, altura))

    def test_caminho_relativo_descarta_repetidos_e_aneis_degenerados(self):
        geometria = feicao(1, [
            [[12, 40], [12.1, 40.1], [15, 38], [15, 43], [12, 40]],
            [[1, 1], [2, 2], [1, 1]],
        ])["geometry"]
        projetar = lambda p: (round(p[0]), round(p[1]))
        self.assertEqual(m.caminho(geometria, projetar), "M12 40l3 -2l0 5z")
        geometria = feicao(1, [geometria["coordinates"], [[[0, 0], [2, 0], [0, 2], [0, 0]]]],
                           "MultiPolygon")["geometry"]
        self.assertEqual(m.caminho(geometria, projetar), "M12 40l3 -2l0 5zM0 0l2 0l-2 2z")

    def test_rotulo_centroide_do_maior_anel(self):
        pequeno = [[100, 100], [101, 100], [100, 101], [100, 100]]
        grande = [[0, 0], [12, 0], [0, 6], [0, 0]]
        geometria = feicao(1, [[pequeno], [list(reversed(grande))]], "MultiPolygon")["geometry"]
        self.assertEqual(m.rotulo(geometria, lambda p: tuple(p)), (4, 2))

    def test_fila_soma_secoes_e_municipios_sem_media_de_percentuais(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            q.escrever_json(pasta / "a.json", dados_municipio([10, 20], [3, 5]))
            q.escrever_json(pasta / "b.json", dados_municipio([50], [10]))
            a = m.totais_fila(pasta / "a.json")
            b = m.totais_fila(pasta / "b.json")
            self.assertEqual(a, (10, 40))
            self.assertEqual(b, (12, 60))
            self.assertEqual(m.percentual(*a), 25.0)
            self.assertEqual(m.percentual(*b), 20.0)
            self.assertEqual(m.percentual(a[0] + b[0], a[1] + b[1]), 22.0)
            self.assertEqual(m.totais_fila(pasta / "ausente.json"), (0, 0))
            q.escrever_json(pasta / "zero.json", {"secoes": {"s": {"3220": {"eleitores": [0], "fila": [0]}}}})
            self.assertIsNone(m.percentual(*m.totais_fila(pasta / "zero.json")))
            self.assertEqual(m.percentual(1, 3), 33.3)

    def rodada(self, destino, sem_contorno=False, ausente=False):
        q.escrever_json(destino / "pb" / "index.json", [["19313", "BANANEIRAS"], ["20000", "ÁGUA BRANCA"]])
        q.escrever_json(destino / "pb" / "19313.json", dados_municipio([10, 20], [3, 5]))
        if not ausente:
            q.escrever_json(destino / "pb" / "20000.json", dados_municipio([50], [10]))
        localidades = [
            {"municipio-id": 2501508, "municipio-nome": "Bananeiras", "UF-id": 25, "UF-sigla": "PB"},
            {"municipio-id": 2500106, "municipio-nome": "Água Branca", "UF-id": 25, "UF-sigla": "PB"},
        ]
        a = [[0, 0], [1, 0], [1, 2], [0, 2], [0, 0]]
        b = [[1, 0], [2, 0], [2, 2], [1, 2], [1, 0]]
        uf = [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]
        municipios = [feicao(2501508, [a])]
        if not sem_contorno:
            municipios.append(feicao(2500106, [[b]], "MultiPolygon"))
        respostas = {LOCALIDADES: gzip.compress(json.dumps(localidades).encode()),
                     BRASIL: json.dumps(colecao(feicao(25, [uf]))).encode(),
                     ESTADO: gzip.compress(json.dumps(colecao(*municipios)).encode())}
        saida, erro = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(q, "baixar", side_effect=respostas.__getitem__),
            redirect_stdout(saida),
            redirect_stderr(erro),
        ):
            retorno = m.main(["--saida", str(destino)])
        return retorno, saida.getvalue(), erro.getvalue()

    def test_rodada_completa_gzip_esquema_e_resumo(self):
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d)
            retorno, saida, erro = self.rodada(destino)
            self.assertEqual(retorno, 0)
            self.assertEqual(saida, "1 UFs, 2 municípios, 0 sem contorno\n")
            self.assertEqual(erro, "")
            br = json.loads((destino / "mapa" / "br.json").read_text(encoding="utf-8"))
            uf = json.loads((destino / "mapa" / "pb.json").read_text(encoding="utf-8"))
            self.assertEqual(br, {"w": 1000, "h": 1000, "ufs": {"pb": {
                "d": "M0 1000l1000 0l0 -1000l-1000 0z", "pct": 22.0, "x": 500, "y": 500}}})
            self.assertEqual(uf, {"w": 1000, "h": 1000, "muns": {
                "19313": {"d": "M0 1000l500 0l0 -1000l-500 0z", "pct": 25.0},
                "20000": {"d": "M500 1000l500 0l0 -1000l-500 0z", "pct": 20.0}}})

    def test_sem_contorno_lista_municipio_e_retorna_um(self):
        with tempfile.TemporaryDirectory() as d:
            retorno, saida, erro = self.rodada(Path(d), sem_contorno=True)
            self.assertEqual(retorno, 1)
            self.assertEqual(saida, "1 UFs, 2 municípios, 1 sem contorno\n")
            self.assertIn("pb/20000", erro)
            self.assertIn("ÁGUA BRANCA", erro)

    def test_arquivo_ausente_preserva_contorno_com_pct_none(self):
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d)
            retorno, _, _ = self.rodada(destino, ausente=True)
            self.assertEqual(retorno, 0)
            uf = json.loads((destino / "mapa" / "pb.json").read_text(encoding="utf-8"))
            br = json.loads((destino / "mapa" / "br.json").read_text(encoding="utf-8"))
            self.assertIsNone(uf["muns"]["20000"]["pct"])
            self.assertEqual(br["ufs"]["pb"]["pct"], 25.0)


if __name__ == "__main__":
    unittest.main()
