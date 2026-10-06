import http.client
import io
import json
import urllib.error
import zipfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
