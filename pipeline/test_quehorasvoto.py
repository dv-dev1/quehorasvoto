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
