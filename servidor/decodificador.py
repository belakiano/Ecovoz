"""Decodificador da carga útil de 12 bytes do alerta EcoVoz.

Layout idêntico a nucleo/alerta.hpp (grande-endiano):
  0-1 sensor | 2-4 latitude | 5-7 longitude | 8 classe(4b)+sinais(4b) | 9 confiança | 10 bateria | 11 idade do evento (s)
"""
from dataclasses import dataclass, asdict

TAM = 12
CLASSES = {0: "batimento", 1: "motosserra", 2: "motor", 3: "fogo"}
SIN_POSICAO_GNSS, SIN_ATUALIZACAO, SIN_BATERIA_BAIXA, SIN_REINICIO = 1, 2, 4, 8
L = 1 << 24


@dataclass
class Alerta:
    sensor: int
    latitude: float
    longitude: float
    classe: int
    sinais: int
    confianca: float      # 0 a 1
    bateria: int          # 0 a 100
    idade_s: int

    @property
    def classe_nome(self):
        return CLASSES.get(self.classe, f"desconhecida_{self.classe}")

    def para_dict(self):
        d = asdict(self)
        d["classe_nome"] = self.classe_nome
        d["posicao_por_gnss"] = bool(self.sinais & SIN_POSICAO_GNSS)
        d["atualizacao"] = bool(self.sinais & SIN_ATUALIZACAO)
        d["bateria_baixa"] = bool(self.sinais & SIN_BATERIA_BAIXA)
        d["reinicio"] = bool(self.sinais & SIN_REINICIO)
        return d


def decodificar(dados: bytes) -> Alerta:
    if len(dados) != TAM:
        raise ValueError(f"carga útil deve ter {TAM} bytes, recebeu {len(dados)}")
    ila = int.from_bytes(dados[2:5], "big")
    ilo = int.from_bytes(dados[5:8], "big")
    lat = ila / L * 180.0 - 90.0
    lon = ilo / L * 360.0 - 180.0
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("coordenadas fora da faixa")
    return Alerta(
        sensor=int.from_bytes(dados[0:2], "big"), latitude=lat, longitude=lon,
        classe=dados[8] >> 4, sinais=dados[8] & 0x0F,
        confianca=dados[9] / 255.0, bateria=min(dados[10], 100), idade_s=dados[11],
    )


def codificar(sensor, latitude, longitude, classe, sinais=0, confianca=0.0, bateria=100, idade_s=0) -> bytes:
    """Usado nos testes e em simuladores. Espelha empacotar() do C++."""
    la = min(max(round((latitude + 90.0) / 180.0 * L), 0), L - 1)
    lo = min(max(round((longitude + 180.0) / 360.0 * L), 0), L - 1)
    return (sensor.to_bytes(2, "big") + la.to_bytes(3, "big") + lo.to_bytes(3, "big")
            + bytes([(classe & 0x0F) << 4 | (sinais & 0x0F), min(max(round(confianca * 255), 0), 255),
                     min(max(bateria, 0), 100), min(max(idade_s, 0), 255)]))
