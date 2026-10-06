import http.client
import io
import json
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

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

    def test_deflate_corrompido_e_none(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("logd.dat", FIXTURE.encode("latin1"))
            info = z.getinfo("logd.dat")
        dados = bytearray(buf.getvalue())
        inicio = info.header_offset + 30 + len(info.filename.encode("ascii")) + len(info.extra)
        meio = inicio + info.compress_size // 2
        for i in range(meio, meio + 20):
            dados[i] ^= 0xff
        self.assertIsNone(q.ler_jez(dados))

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
        self.assertIsNone(q.baixar("https://example.com/", espera=0))
        self.assertEqual(urlopen.call_count, 1)

    @mock.patch("quehorasvoto.urllib.request.urlopen")
    def test_503_retenta(self, urlopen):
        urlopen.side_effect = [http_erro(503), io.BytesIO(b"ok")]
        self.assertEqual(q.baixar("https://example.com/", espera=0), b"ok")

    @mock.patch("quehorasvoto.urllib.request.urlopen")
    def test_leitura_incompleta_retenta(self, urlopen):
        resposta = mock.MagicMock()
        resposta.__enter__.return_value = resposta
        resposta.read.side_effect = http.client.IncompleteRead(b"")
        urlopen.side_effect = [resposta, io.BytesIO(b"ok")]
        self.assertEqual(q.baixar("https://example.com/", espera=0), b"ok")

    @mock.patch("quehorasvoto.urllib.request.urlopen")
    def test_403_persistente_levanta(self, urlopen):
        urlopen.side_effect = [http_erro(403)] * 4
        with self.assertRaises(urllib.error.HTTPError):
            q.baixar("https://example.com/", espera=0)
        self.assertEqual(urlopen.call_count, 4)


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


if __name__ == "__main__":
    unittest.main()
