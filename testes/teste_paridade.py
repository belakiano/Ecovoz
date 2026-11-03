"""Confere que o extrator C++ (nucleo/atributos.hpp) e o Python (treino/atributos.py) dão a mesma saída."""
import subprocess, sys, tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "treino"))
import atributos as A

CLI = RAIZ / "testes" / "cli_atributos"
ESC = RAIZ / "dados" / "ESC-50"

def janela_esc(nome, inicio_s=1.0):
    taxa, x = wavfile.read(ESC / "audio" / nome)
    x = x.astype(np.float32) / 32768.0
    y = resample_poly(x, 160, 441)
    i = int(inicio_s * 16000)
    return np.clip(np.round(y[i:i + 16000] * 32768), -32768, 32767).astype(np.int16)

def cpp(pcm):
    with tempfile.TemporaryDirectory() as d:
        e, s = Path(d) / "e.pcm", Path(d) / "s.f32"
        e.write_bytes(pcm.astype("<i2").tobytes())
        subprocess.run([str(CLI), str(e), str(s)], check=True)
        return np.fromfile(s, dtype="<f4").reshape(A.N_QUADROS, A.N_MELS)

def casos():
    import csv
    meta = list(csv.DictReader(open(ESC / "meta" / "esc50.csv")))
    por_cat = {}
    for l in meta:
        por_cat.setdefault(l["category"], l["filename"])
    rng = np.random.default_rng(7)
    c = {
        "silencio_total": np.zeros(16000, np.int16),
        "ruido_branco_forte": (rng.standard_normal(16000) * 8000).clip(-32768, 32767).astype(np.int16),
        "ruido_muito_fraco": (rng.standard_normal(16000) * 3).astype(np.int16),
        "senoide_1kHz": (np.sin(2 * np.pi * 1000 * np.arange(16000) / 16000) * 20000).astype(np.int16),
        "saturado": np.where(np.arange(16000) % 2 == 0, 32767, -32768).astype(np.int16),
        "com_offset_DC": (rng.standard_normal(16000) * 2000 + 5000).clip(-32768, 32767).astype(np.int16),
    }
    for cat in ("chainsaw", "engine", "rain", "wind", "thunderstorm", "insects", "frog", "crickets"):
        c[f"esc50_{cat}"] = janela_esc(por_cat[cat])
    return c

if __name__ == "__main__":
    mu, sd = A.carregar_normalizacao()
    print(f"normalização usada: média={mu:.4f} desvio={sd:.4f}")
    # Sinais patológicos (tom puro e onda quadrada em fundo de escala) têm bins abaixo do ruído de
    # quantização de 16 bits, onde o resultado é ruído de arredondamento da FFT. Recebem tolerância maior.
    PATOLOGICOS = {"senoide_1kHz", "saturado"}
    LIM_REAL, LIM_PATOL = 1e-4, 3e-2   # o degrau de quantização int8 da entrada do modelo fica em torno de 3e-2
    falhas = []
    for nome, pcm in casos().items():
        ref, got = A.extrair(pcm), cpp(pcm)
        err = np.abs(ref - got)
        lim = LIM_PATOL if nome in PATOLOGICOS else LIM_REAL
        marca = "ok " if err.max() < lim else "FALHA"
        if err.max() >= lim:
            falhas.append(nome)
        print(f"  {marca} {nome:22s} erro máx {err.max():.2e}  médio {err.mean():.2e}  limite {lim:.0e}")
    print("APROVADO" if not falhas else f"REPROVADO: {falhas}")
    sys.exit(0 if not falhas else 1)
