# buscador

Busca passagens aéreas e procura **rotas alternativas mais baratas**: aeroportos próximos, datas flexíveis e conexões montadas com duas passagens separadas.

Consulta o Google Flights direto por código (sem navegador, sem prints, sem API paga). Cada busca leva cerca de 1 segundo, e várias rodam em paralelo.

## Instalação

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Uso

```bash
# Cidade → cidade (testa todos os aeroportos de cada uma + conexões)
.venv/bin/python -m buscador "São Paulo" "Buenos Aires" 2026-12-10

# Datas flexíveis (±2 dias)
.venv/bin/python -m buscador SP "Buenos Aires" 2026-12-10 --flex 2

# Só aquele aeroporto, sem conexões montadas
.venv/bin/python -m buscador GRU EZE 2026-12-10 --exato --sem-conexoes

# Forçar as cidades de conexão
.venv/bin/python -m buscador SP Bariloche 2027-01-15 --via POA,SCL

# Saída em JSON (para usar em um bot)
.venv/bin/python -m buscador SP BUE 2026-12-10 --json
```

| Opção | O que faz |
|---|---|
| `--flex N` | testa N dias antes e depois |
| `--exato` | não testa aeroportos próximos (CGH/VCP para GRU etc.) |
| `--sem-conexoes` | só passagens únicas |
| `--via A,B` | cidades de conexão a testar (padrão: lista em `aeroportos.py`) |
| `--min-conexao H` | horas mínimas entre passagens separadas (padrão 3) |
| `--top N` | quantas opções mostrar |

## Como funciona

1. `aeroportos.py` transforma "São Paulo" em GRU/CGH/VCP e escolhe as cidades de conexão.
2. `motor.py` gera todas as buscas: diretas (origens × destinos × datas), origem → conexão e conexão → destino (no mesmo dia e no dia seguinte).
3. `fonte.py` consulta o Google Flights em paralelo e lê os resultados.
4. As passagens separadas só são combinadas se a conexão tiver entre 3h e 20h. O resultado é um ranking por preço.

## Limitações (importante)

- **Não é uma API oficial.** Se o Google mudar a página, `fonte.py` pode parar de funcionar e precisar de ajuste.
- **Passagens separadas têm risco.** Se o 1º voo atrasar, a 2ª companhia não remarca, e a bagagem precisa ser despachada de novo. O programa avisa em cada opção.
- **Os preços mudam o tempo todo.** Confirme no site antes de comprar. A compra é feita por você.
- Por enquanto só busca **ida**. Para ida e volta, rode duas buscas.
- Bagagem despachada não entra no preço.

## Testes

```bash
.venv/bin/pip install pytest
.venv/bin/pytest -q
```
