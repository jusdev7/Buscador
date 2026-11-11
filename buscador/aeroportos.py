"""Aeroportos próximos e cidades de conexão.

Lista curta e editável, focada em Brasil e América do Sul. Para incluir uma
cidade nova, adicione-a em CIDADES (e, se fizer sentido, em HUBS).
"""

# Código da cidade (ou apelido) → aeroportos que atendem essa cidade.
CIDADES: dict[str, list[str]] = {
    "SAO": ["GRU", "CGH", "VCP"],
    "RIO": ["GIG", "SDU"],
    "BHZ": ["CNF", "PLU"],
    "BUE": ["EZE", "AEP"],
    "BSB": ["BSB"],
    "POA": ["POA"],
    "FLN": ["FLN"],
    "CWB": ["CWB"],
    "SSA": ["SSA"],
    "REC": ["REC"],
    "FOR": ["FOR"],
    "MVD": ["MVD"],
    "SCL": ["SCL"],
    "ASU": ["ASU"],
    "LIM": ["LIM"],
    "BOG": ["BOG"],
    "COR": ["COR"],
    "MDZ": ["MDZ"],
    "BRC": ["BRC"],
    "IGU": ["IGU"],
    # Ásia
    "TYO": ["NRT", "HND"],
    "OSA": ["KIX"],
    "SEL": ["ICN"],
    "BJS": ["PEK", "PKX"],
    "SHA": ["PVG"],
    "CAN": ["CAN"],
    "HKG": ["HKG"],
}

# País → aeroportos principais (para "o destino mais barato do país").
PAISES: dict[str, list[str]] = {
    "JAPAO": ["NRT", "HND", "KIX"],
    "COREIA": ["ICN"],
    "CHINA": ["PEK", "PKX", "PVG", "CAN"],
}

APELIDOS: dict[str, str] = {
    "SAO PAULO": "SAO",
    "SÃO PAULO": "SAO",
    "SP": "SAO",
    "RIO DE JANEIRO": "RIO",
    "RIO": "RIO",
    "BELO HORIZONTE": "BHZ",
    "BH": "BHZ",
    "BUENOS AIRES": "BUE",
    "BRASILIA": "BSB",
    "BRASÍLIA": "BSB",
    "PORTO ALEGRE": "POA",
    "FLORIANOPOLIS": "FLN",
    "FLORIANÓPOLIS": "FLN",
    "CURITIBA": "CWB",
    "SALVADOR": "SSA",
    "RECIFE": "REC",
    "FORTALEZA": "FOR",
    "MONTEVIDEU": "MVD",
    "MONTEVIDÉU": "MVD",
    "SANTIAGO": "SCL",
    "ASSUNCAO": "ASU",
    "ASSUNÇÃO": "ASU",
    "LIMA": "LIM",
    "BOGOTA": "BOG",
    "BOGOTÁ": "BOG",
    "CORDOBA": "COR",
    "CÓRDOBA": "COR",
    "MENDOZA": "MDZ",
    "BARILOCHE": "BRC",
    "FOZ DO IGUACU": "IGU",
    "FOZ DO IGUAÇU": "IGU",
    "TOQUIO": "TYO",
    "TÓQUIO": "TYO",
    "OSAKA": "OSA",
    "SEUL": "SEL",
    "PEQUIM": "BJS",
    "XANGAI": "SHA",
    "HONG KONG": "HKG",
    "JAPÃO": "JAPAO",
    "JAPAN": "JAPAO",
    "COREIA DO SUL": "COREIA",
    "CORÉIA": "COREIA",
}

# Cidades por onde vale testar uma conexão montada (duas passagens separadas).
HUBS: list[str] = ["GRU", "GIG", "BSB", "FLN", "POA", "CWB", "IGU", "MVD", "ASU", "SCL", "LIM"]

# Conexões para voos de longa distância (Ásia, Europa...).
HUBS_LONGOS: list[str] = [
    "DOH", "DXB", "AUH", "IST", "ADD",  # Oriente Médio / África
    "CDG", "FRA", "AMS", "MAD", "LIS", "ZRH", "LHR",  # Europa
    "JFK", "LAX", "IAH",  # EUA (exige visto americano mesmo só de conexão)
]

# Países com exigência de visto/autorização só para trocar de voo (passagem separada).
_EUA = ["JFK", "EWR", "LAX", "SFO", "SEA", "IAH", "DFW", "ORD", "ATL", "MIA", "IAD", "BOS", "DTW", "MSP", "PHX", "MCO"]
HUBS_COM_VISTO = {**{a: "EUA" for a in _EUA}, "YYZ": "Canadá", "YVR": "Canadá", "YUL": "Canadá", "LHR": "Reino Unido (ETA)"}

_AMERICA_DO_SUL = {"GRU", "CGH", "VCP", "GIG", "SDU", "CNF", "PLU", "BSB", "POA", "FLN", "CWB", "SSA", "REC",
                   "FOR", "EZE", "AEP", "MVD", "SCL", "ASU", "LIM", "BOG", "COR", "MDZ", "BRC", "IGU"}

# Aeroporto → cidade (para não usar como conexão um aeroporto da própria origem/destino).
_CIDADE_DO_AEROPORTO = {a: c for c, aeros in CIDADES.items() for a in aeros}


def resolver(lugar: str, *, proximos: bool = True) -> list[str]:
    """'São Paulo' → ['GRU','CGH','VCP']; 'GRU' → ['GRU'] (ou a cidade toda se proximos).

    Aceita vários lugares separados por vírgula e nomes de país ('Japão').
    """
    if "," in lugar:
        out: list[str] = []
        for parte in lugar.split(","):
            out += [a for a in resolver(parte, proximos=proximos) if a not in out]
        return out
    chave = lugar.strip().upper()
    chave = APELIDOS.get(chave, chave)
    if chave in PAISES:
        return list(PAISES[chave])
    if chave in CIDADES:
        return list(CIDADES[chave]) if proximos else CIDADES[chave][:1]
    if proximos and chave in _CIDADE_DO_AEROPORTO:
        cidade = CIDADES[_CIDADE_DO_AEROPORTO[chave]]
        return [chave] + [a for a in cidade if a != chave]
    if len(chave) == 3 and chave.isalpha():
        return [chave]
    raise ValueError(f"Não conheço '{lugar}'. Use o código IATA (ex.: GRU) ou adicione em aeroportos.py")


def cidade(aeroporto: str) -> str:
    return _CIDADE_DO_AEROPORTO.get(aeroporto, aeroporto)


def hubs_para(origens: list[str], destinos: list[str]) -> list[str]:
    excluir = {cidade(a) for a in origens + destinos}
    regional = all(a in _AMERICA_DO_SUL for a in origens + destinos)
    return [h for h in (HUBS if regional else HUBS_LONGOS) if cidade(h) not in excluir]
