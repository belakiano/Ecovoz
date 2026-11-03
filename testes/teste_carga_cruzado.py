"""Compara byte a byte o empacotador C++ (nucleo/alerta.hpp) com o codificador/decodificador Python do servidor."""
import random, subprocess, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "servidor"))
import decodificador as D

EXE = str(RAIZ / "testes" / "teste_alerta")
rnd = random.Random(2026)
casos = [(1, -90.0, -180.0, 1, 0, 0, 0, 0), (65535, 89.9999999, 179.9999999, 3, 15, 255, 100, 255), (402, -5.7333, -52.65, 1, 1, 251, 88, 12)]
for _ in range(1000):
    casos.append((rnd.randrange(65536), rnd.uniform(-33.8, 5.3), rnd.uniform(-74.0, -34.7),   # caixa envolvente do Brasil
                  rnd.randrange(4), rnd.randrange(16), rnd.randrange(256), rnd.randrange(101), rnd.randrange(256)))

entrada = "\n".join(" ".join(repr(v) if isinstance(v, float) else str(v) for v in c) for c in casos) + "\n"
hex_cpp = subprocess.run([EXE, "empacotar"], input=entrada, capture_output=True, text=True, check=True).stdout.split()
assert len(hex_cpp) == len(casos)

difer = 0; pior_pos_m = 0.0; pior_br = 0.0
for c, h in zip(casos, hex_cpp):
    sensor, lat, lon, cl, sin, conf, bat, idade = c
    esperado = D.codificar(sensor, lat, lon, cl, sin, conf / 255.0, bat, idade).hex()
    if esperado != h:
        difer += 1
        if difer <= 3: print("difere:", c, esperado, h)
    a = D.decodificar(bytes.fromhex(h))
    assert (a.sensor, a.classe, a.sinais, a.bateria, a.idade_s) == (sensor, cl, sin, bat, idade)
    assert round(a.confianca * 255) == conf
    e = max(abs(a.latitude - lat) * 111_320, abs(a.longitude - lon) * 111_320 * 0.97)
    pior_pos_m = max(pior_pos_m, e)
    if c is not casos[0] and c is not casos[1]: pior_br = max(pior_br, e)
print(f"{len(casos)} casos: {difer} bytes divergentes entre C++ e Python; erro máximo de posição {pior_pos_m:.2f} m (extremos do globo); sem os 2 casos extremos {pior_br:.2f} m")

# sentido contrário: Python codifica, C++ decodifica
hexes = "\n".join(D.codificar(c[0], c[1], c[2], c[3], c[4], c[5] / 255.0, c[6], c[7]).hex() for c in casos) + "\n"
saida = subprocess.run([EXE, "desempacotar"], input=hexes, capture_output=True, text=True, check=True).stdout.strip().split("\n")
for c, linha in zip(casos, saida):
    f = linha.split(); a = D.decodificar(bytes.fromhex(D.codificar(c[0], c[1], c[2], c[3], c[4], c[5] / 255.0, c[6], c[7]).hex()))
    assert int(f[0]) == a.sensor and abs(float(f[1]) - a.latitude) < 1e-8 and abs(float(f[2]) - a.longitude) < 1e-8
    assert (int(f[3]), int(f[4]), int(f[5]), int(f[6]), int(f[7])) == (a.classe, a.sinais, c[5], a.bateria, a.idade_s)
print("decodificação C++ igual à do Python nos mesmos casos")
sys.exit(1 if difer else 0)
