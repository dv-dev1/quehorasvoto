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
