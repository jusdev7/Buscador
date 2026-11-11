"""Busca voos no Google Flights (sem navegador, sem API oficial).

Usa a biblioteca `fast-flights` só para montar a URL de busca e baixar o HTML.
A leitura dos dados é feita aqui, de forma tolerante: um item malformado é
ignorado em vez de derrubar a busca inteira (a biblioteca original quebra
quando algum voo aparece sem preço).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime

from fast_flights import FlightQuery, create_query, fetch_flights_html
from selectolax.lexbor import LexborHTMLParser


class FonteIndisponivel(Exception):
    """O Google não respondeu do jeito esperado (mudou a página, bloqueou etc.)."""


@dataclass(frozen=True)
class Segmento:
    origem: str
    destino: str
    partida: datetime
    chegada: datetime
    cia: str
    numero: str  # ex.: "LA 8022"


@dataclass(frozen=True)
class Itinerario:
    """Uma passagem: um ou mais segmentos vendidos juntos, com um preço."""

    preco: int  # na moeda pedida (padrão BRL)
    cias: tuple[str, ...]
    segmentos: tuple[Segmento, ...]

    @property
    def origem(self) -> str:
        return self.segmentos[0].origem

    @property
    def destino(self) -> str:
        return self.segmentos[-1].destino

    @property
    def partida(self) -> datetime:
        return self.segmentos[0].partida

    @property
    def chegada(self) -> datetime:
        return self.segmentos[-1].chegada

    @property
    def paradas(self) -> int:
        return len(self.segmentos) - 1

    @property
    def rota(self) -> str:
        return " → ".join([self.origem] + [s.destino for s in self.segmentos])


def _hora(valor) -> tuple[int, int]:
    # O Google omite componentes zero: [8] = 08:00, [None, 31] = 00:31.
    v = [*(valor or []), None, None]
    return (v[0] or 0, v[1] or 0)


def _datahora(data, hora) -> datetime:
    h, m = _hora(hora)
    return datetime(data[0], data[1], data[2], h, m)


def _segmento(s) -> Segmento:
    voo = s[22] or []
    return Segmento(
        origem=s[3],
        destino=s[6],
        partida=_datahora(s[20], s[8]),
        chegada=_datahora(s[21], s[10]),
        cia=(voo[3] if len(voo) > 3 and voo[3] else s[2]) or "?",
        numero=f"{voo[0]} {voo[1]}" if len(voo) > 1 else "",
    )


def ler_html(html: str) -> list[Itinerario]:
    """Extrai os itinerários do HTML do Google Flights."""
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        raise FonteIndisponivel("bloco de dados não encontrado na página")
    js = script.text()
    try:
        payload = json.loads(js.split("data:", 1)[1].rsplit(",", 1)[0])
    except (IndexError, ValueError) as e:
        raise FonteIndisponivel(f"dados em formato inesperado: {e}") from e
    return ler_payload(payload)


def ler_payload(payload) -> list[Itinerario]:
    vistos: set = set()
    saida: list[Itinerario] = []
    # payload[2] = "melhores voos", payload[3] = "outros voos"
    for idx in (2, 3):
        bloco = payload[idx] if len(payload) > idx else None
        for item in ((bloco or [None])[0] or []):
            try:
                voo, preco = item[0], item[1][0][1]
                if not preco:
                    continue
                it = Itinerario(
                    preco=int(preco),
                    cias=tuple(voo[1] or ()),
                    segmentos=tuple(_segmento(s) for s in voo[2]),
                )
            except (IndexError, TypeError, ValueError):
                continue  # item sem preço ou malformado: ignora só ele
            chave = (it.preco, tuple((s.numero, s.partida) for s in it.segmentos))
            if chave not in vistos:
                vistos.add(chave)
                saida.append(it)
    return sorted(saida, key=lambda i: i.preco)


def buscar(
    origem: str,
    destino: str,
    data: str,
    *,
    moeda: str = "BRL",
    idioma: str = "pt-BR",
    tentativas: int = 3,
) -> list[Itinerario]:
    """Busca passagens só de ida. `data` no formato AAAA-MM-DD.

    Retorna lista vazia se não houver voos; levanta FonteIndisponivel se
    todas as tentativas falharem.
    """
    q = create_query(
        flights=[FlightQuery(date=data, from_airport=origem, to_airport=destino)],
        trip="one-way",
        language=idioma,
        currency=moeda,
    )
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    erro: Exception | None = None
    for i in range(tentativas):
        try:
            return ler_html(fetch_flights_html(q, proxy=proxy))
        except Exception as e:  # rede instável, resposta cortada etc.
            erro = e
            time.sleep(1 + i)
    raise FonteIndisponivel(f"{origem}→{destino} {data}: {erro}")
