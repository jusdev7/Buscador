from datetime import date, datetime, timedelta

import pytest

from buscador import aeroportos
from buscador.fonte import FonteIndisponivel, Itinerario, Segmento, ler_payload
from buscador.motor import combinar, pesquisar

AMANHA = (date.today() + timedelta(days=30)).isoformat()


def it(o, d, preco, sai, chega, cia="X"):
    return Itinerario(preco, (cia,), (Segmento(o, d, sai, chega, cia, f"{cia} 1"),))


def dt(h, dia=0):
    base = datetime.fromisoformat(AMANHA)
    return base + timedelta(days=dia, hours=h)


def test_resolver_cidade_e_apelido():
    assert aeroportos.resolver("São Paulo") == ["GRU", "CGH", "VCP"]
    assert aeroportos.resolver("GRU") == ["GRU", "CGH", "VCP"]
    assert aeroportos.resolver("GRU", proximos=False) == ["GRU"]
    assert aeroportos.resolver("xyz") == ["XYZ"]
    with pytest.raises(ValueError):
        aeroportos.resolver("Lugar Inventado")


def test_hubs_excluem_origem_e_destino():
    hubs = aeroportos.hubs_para(["GRU", "CGH"], ["EZE"])
    assert "GRU" not in hubs and "POA" in hubs


def test_combinar_respeita_tempo_de_conexao():
    a = it("GRU", "POA", 300, dt(8), dt(10))
    curta = it("POA", "EZE", 200, dt(11), dt(13))  # 1h: perigoso
    boa = it("POA", "EZE", 400, dt(14), dt(16))  # 4h: ok
    op = combinar([a], [curta, boa], min_conexao=timedelta(hours=3), max_conexao=timedelta(hours=20))
    assert op.preco == 700 and op.trechos[1] is boa


def test_combinar_rejeita_aeroporto_diferente():
    a = it("GRU", "GIG", 300, dt(8), dt(9))
    b = it("SDU", "EZE", 200, dt(14), dt(17))
    assert combinar([a], [b], min_conexao=timedelta(hours=3), max_conexao=timedelta(hours=20)) is None


def test_pesquisar_encontra_separada_mais_barata():
    voos = {
        ("GRU", "EZE"): [it("GRU", "EZE", 1000, dt(9), dt(12))],
        ("GRU", "FLN"): [it("GRU", "FLN", 200, dt(7), dt(8))],
        ("FLN", "EZE"): [it("FLN", "EZE", 300, dt(12), dt(14))],
    }

    def fonte(o, d, data):
        if (o, d) == ("GRU", "POA"):
            raise FonteIndisponivel("simulada")
        return voos.get((o, d), []) if data == AMANHA else []

    r = pesquisar("GRU", "EZE", AMANHA, proximos=False, hubs=["FLN", "POA"], fonte=fonte)
    assert [o.tipo for o in r.opcoes] == ["separada", "direta"]
    assert r.opcoes[0].preco == 500
    assert r.opcoes[0].rota == "GRU → FLN → EZE"
    assert ("GRU", "POA", AMANHA) in r.buscas_falharam


def test_ler_payload_ignora_item_sem_preco():
    seg = [None, None, "Cia", "GRU", "", "", "EZE", None, [13], None, [16], 180,
           None, None, None, None, None, "A321", None, 0, [2026, 12, 10], [2026, 12, 10],
           ["LA", "8022", None, "LATAM"]]
    bom = [["LA", ["LATAM"], [seg]], [[None, 700], "tok"]]
    sem_preco = [["LA", ["LATAM"], [seg]], [[None]]]
    payload = [None, None, [[sem_preco, bom]], [None]]
    r = ler_payload(payload)
    assert len(r) == 1 and r[0].preco == 700
    assert r[0].segmentos[0].numero == "LA 8022"
    assert r[0].partida == datetime(2026, 12, 10, 13, 0)


def test_resolver_paises_e_lista():
    r = aeroportos.resolver("Japão,Coreia,China")
    assert r[:4] == ["NRT", "HND", "KIX", "ICN"] and "PVG" in r


def test_hubs_longos_para_asia():
    hubs = aeroportos.hubs_para(["GRU"], ["NRT"])
    assert "DOH" in hubs and "POA" not in hubs


def test_aviso_de_visto_em_conexao_nos_eua():
    from buscador.motor import _avisos_visto
    s1 = Segmento("GRU", "JFK", dt(0), dt(10), "AA", "AA 1")
    s2 = Segmento("JFK", "HND", dt(12), dt(26), "AA", "AA 2")
    assert _avisos_visto(Itinerario(5000, ("AA",), (s1, s2)))
    assert not _avisos_visto(it("GRU", "JFK", 3000, dt(0), dt(10)))
