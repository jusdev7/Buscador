"""Motor de busca: gera as combinações, consulta em paralelo e monta o ranking."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable

from fast_flights import FlightQuery, create_query

from . import aeroportos
from .fonte import FonteIndisponivel, Itinerario, buscar

Busca = tuple[str, str, str]  # (origem, destino, AAAA-MM-DD)


@dataclass
class Opcao:
    tipo: str  # "direta" (uma passagem) ou "separada" (duas passagens)
    preco: int
    trechos: tuple[Itinerario, ...]
    avisos: list[str] = field(default_factory=list)

    @property
    def rota(self) -> str:
        partes = [self.trechos[0].rota]
        for t in self.trechos[1:]:
            partes.append(t.rota.split(" → ", 1)[1])
        return " → ".join(partes)

    @property
    def partida(self) -> datetime:
        return self.trechos[0].partida

    @property
    def chegada(self) -> datetime:
        return self.trechos[-1].chegada

    def links(self) -> list[str]:
        return [link_google(t.origem, t.destino, t.partida.strftime("%Y-%m-%d")) for t in self.trechos]


@dataclass
class Resultado:
    opcoes: list[Opcao]
    buscas_feitas: int
    buscas_falharam: list[Busca]
    segundos: float


def link_google(origem: str, destino: str, data: str) -> str:
    q = create_query(
        flights=[FlightQuery(date=data, from_airport=origem, to_airport=destino)],
        trip="one-way",
        language="pt-BR",
        currency="BRL",
    )
    return q.url()


def _datas(base: str, flex: int) -> list[str]:
    d0 = date.fromisoformat(base)
    hoje = date.today()
    ds = [d0 + timedelta(days=i) for i in range(-flex, flex + 1)]
    return [d.isoformat() for d in ds if d >= hoje]


def _mais_um_dia(d: str) -> str:
    return (date.fromisoformat(d) + timedelta(days=1)).isoformat()


def planejar(
    origens: list[str],
    destinos: list[str],
    datas: list[str],
    hubs: list[str],
) -> tuple[list[Busca], list[Busca], list[Busca]]:
    """Retorna (buscas diretas, 1º trecho via hub, 2º trecho via hub)."""
    diretas = [(o, d, dt) for dt in datas for o in origens for d in destinos]
    ida_hub = [(o, h, dt) for dt in datas for o in origens for h in hubs]
    datas_2 = sorted(set(datas) | {_mais_um_dia(dt) for dt in datas})
    hub_dest = [(h, d, dt) for dt in datas_2 for h in hubs for d in destinos]
    return diretas, ida_hub, hub_dest


def combinar(
    leg1: list[Itinerario],
    leg2: list[Itinerario],
    *,
    min_conexao: timedelta,
    max_conexao: timedelta,
) -> Opcao | None:
    """Melhor par (1º trecho, 2º trecho) com tempo de conexão seguro."""
    melhor: Opcao | None = None
    for a in leg1[:15]:
        for b in leg2[:15]:
            if a.destino != b.origem:
                continue
            espera = b.partida - a.chegada
            if not (min_conexao <= espera <= max_conexao):
                continue
            total = a.preco + b.preco
            if melhor is None or total < melhor.preco:
                melhor = Opcao("separada", total, (a, b), _avisos_separada(a, b, espera))
    return melhor


def _avisos_separada(a: Itinerario, b: Itinerario, espera: timedelta) -> list[str]:
    h = int(espera.total_seconds() // 3600)
    m = int(espera.total_seconds() % 3600 // 60)
    av = [
        f"Duas passagens separadas, com conexão de {h}h{m:02d} em {a.destino}. "
        "Se o 1º voo atrasar, a 2ª companhia não tem obrigação de remarcar.",
        "Você precisa retirar e despachar a bagagem de novo na conexão.",
    ]
    if a.chegada.date() != b.partida.date():
        av.append(f"A conexão atravessa a noite em {a.destino}.")
    return av


def pesquisar(
    origem: str,
    destino: str,
    data: str,
    *,
    flex: int = 0,
    proximos: bool = True,
    conexoes: bool = True,
    hubs: list[str] | None = None,
    min_conexao_h: float = 3,
    max_conexao_h: float = 20,
    paralelo: int = 6,
    fonte: Callable[[str, str, str], list[Itinerario]] = buscar,
) -> Resultado:
    t0 = time.time()
    origens = aeroportos.resolver(origem, proximos=proximos)
    destinos = aeroportos.resolver(destino, proximos=proximos)
    datas = _datas(data, flex)
    if not datas:
        raise ValueError("A data (e toda a janela de flexibilidade) já passou.")
    if not conexoes:
        hubs = []
    elif hubs is None:
        hubs = aeroportos.hubs_para(origens, destinos)

    diretas, ida_hub, hub_dest = planejar(origens, destinos, datas, hubs)
    todas = list(dict.fromkeys(diretas + ida_hub + hub_dest))

    falhas: list[Busca] = []

    def tarefa(b: Busca) -> list[Itinerario]:
        try:
            return fonte(*b)
        except FonteIndisponivel:
            falhas.append(b)
            return []

    with ThreadPoolExecutor(max(1, paralelo)) as ex:
        res: dict[Busca, list[Itinerario]] = dict(zip(todas, ex.map(tarefa, todas)))

    opcoes: list[Opcao] = []
    for b in diretas:
        if res[b]:
            it = res[b][0]  # já vem ordenado por preço
            opcoes.append(Opcao("direta", it.preco, (it,)))

    lim = (timedelta(hours=min_conexao_h), timedelta(hours=max_conexao_h))
    for o, h, dt in ida_hub:
        leg1 = res[(o, h, dt)]
        if not leg1:
            continue
        for d in destinos:
            leg2 = res.get((h, d, dt), []) + res.get((h, d, _mais_um_dia(dt)), [])
            leg2.sort(key=lambda i: i.preco)
            op = combinar(leg1, leg2, min_conexao=lim[0], max_conexao=lim[1])
            if op:
                opcoes.append(op)

    opcoes.sort(key=lambda o: (o.preco, o.chegada))
    return Resultado(opcoes, len(todas), falhas, time.time() - t0)
