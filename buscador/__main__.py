"""Linha de comando.

Exemplos:
    python -m buscador "São Paulo" "Buenos Aires" 2026-12-10
    python -m buscador GRU EZE 2026-12-10 --flex 2 --exato
    python -m buscador SP Bariloche 2027-01-15 --via POA,SCL --json
"""

from __future__ import annotations

import argparse
import json
import sys

from .motor import Opcao, pesquisar


def _fmt(op: Opcao, n: int) -> str:
    linhas = [f"{n:>2}. R$ {op.preco:>6,}".replace(",", ".") + f"  {op.rota}  [{op.tipo}]"]
    for t in op.trechos:
        voos = ", ".join(f"{s.numero} ({s.cia})" for s in t.segmentos)
        linhas.append(
            f"      {t.origem}→{t.destino}  {t.partida:%d/%m %H:%M} → {t.chegada:%d/%m %H:%M}"
            f"  R$ {t.preco}  {voos}"
        )
    for a in op.avisos:
        linhas.append(f"      ⚠ {a}")
    return "\n".join(linhas)


def _json(op: Opcao) -> dict:
    return {
        "tipo": op.tipo,
        "preco": op.preco,
        "rota": op.rota,
        "partida": op.partida.isoformat(),
        "chegada": op.chegada.isoformat(),
        "avisos": op.avisos,
        "links": op.links(),
        "trechos": [
            {
                "preco": t.preco,
                "rota": t.rota,
                "cias": list(t.cias),
                "segmentos": [
                    {
                        "voo": s.numero,
                        "cia": s.cia,
                        "de": s.origem,
                        "para": s.destino,
                        "partida": s.partida.isoformat(),
                        "chegada": s.chegada.isoformat(),
                    }
                    for s in t.segmentos
                ],
            }
            for t in op.trechos
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="buscador", description="Busca passagens e rotas alternativas mais baratas.")
    p.add_argument("origem", help="cidade ou código IATA (ex.: 'São Paulo', GRU)")
    p.add_argument("destino")
    p.add_argument("data", help="AAAA-MM-DD")
    p.add_argument("--flex", type=int, default=0, help="dias de flexibilidade para mais e para menos")
    p.add_argument("--exato", action="store_true", help="não testar aeroportos próximos")
    p.add_argument("--sem-conexoes", action="store_true", help="não montar conexões com passagens separadas")
    p.add_argument("--via", help="cidades de conexão, separadas por vírgula (ex.: POA,SCL)")
    p.add_argument("--min-conexao", type=float, default=3, help="horas mínimas entre passagens separadas (padrão 3)")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--json", action="store_true", help="saída em JSON")
    a = p.parse_args(argv)

    try:
        r = pesquisar(
            a.origem,
            a.destino,
            a.data,
            flex=a.flex,
            proximos=not a.exato,
            conexoes=not a.sem_conexoes,
            hubs=[h.strip().upper() for h in a.via.split(",")] if a.via else None,
            min_conexao_h=a.min_conexao,
        )
    except ValueError as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 2

    if a.json:
        print(
            json.dumps(
                {
                    "buscas": r.buscas_feitas,
                    "falhas": [list(f) for f in r.buscas_falharam],
                    "segundos": round(r.segundos, 1),
                    "opcoes": [_json(o) for o in r.opcoes[: a.top]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"{r.buscas_feitas} buscas em {r.segundos:.1f}s ({len(r.buscas_falharam)} falharam)\n")
    if not r.opcoes:
        print("Nenhuma opção encontrada.")
        return 1
    melhor_direta = next((o for o in r.opcoes if o.tipo == "direta"), None)
    for i, op in enumerate(r.opcoes[: a.top], 1):
        print(_fmt(op, i))
        if op.tipo == "separada" and melhor_direta and op.preco < melhor_direta.preco:
            print(f"      💰 R$ {melhor_direta.preco - op.preco} mais barato que a melhor passagem única")
        print()
    if r.buscas_falharam:
        print("Buscas que falharam:", ", ".join("→".join(f[:2]) + " " + f[2] for f in r.buscas_falharam))
    return 0


if __name__ == "__main__":
    sys.exit(main())
