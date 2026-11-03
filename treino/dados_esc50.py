"""Carrega o ESC-50, reamostra para 16 kHz e organiza as classes do EcoVoz.

Classes do modelo da fase 1:
  0 ambiente    sons de floresta, chuva, vento, fauna e ruídos difíceis (avião, helicóptero, serra manual)
  1 motosserra  categoria 'chainsaw'
  2 motor       categoria 'engine'
O fogo fica fora da fase 1 (linha experimental separada, conforme o plano de captação).

Licença: o ESC-50 é CC BY-NC 3.0 (uso não comercial). Serve para o protótipo de pesquisa. Para uso
comercial é preciso gravar dados próprios ou usar fontes com licença adequada.
"""
import csv
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

RAIZ = Path(__file__).resolve().parent.parent
ESC = RAIZ / "dados" / "ESC-50"
CACHE = RAIZ / "dados" / "clipes_16k.npz"

NOMES_CLASSES = ["ambiente", "motosserra", "motor"]
POSITIVAS = {"chainsaw": 1, "engine": 2}
AMBIENTE = ["rain", "sea_waves", "wind", "thunderstorm", "crickets", "chirping_birds", "insects", "frog",
            "crow", "water_drops", "pouring_water", "rooster", "hen", "cow", "pig", "sheep", "cat", "dog",
            "airplane", "helicopter", "hand_saw"]

def carregar():
    if CACHE.exists():
        d = np.load(CACHE, allow_pickle=True)
        return d["x"], d["y"], d["fold"], d["cat"]
    meta = list(csv.DictReader(open(ESC / "meta" / "esc50.csv")))
    xs, ys, folds, cats = [], [], [], []
    for l in meta:
        cat = l["category"]
        if cat in POSITIVAS: y = POSITIVAS[cat]
        elif cat in AMBIENTE: y = 0
        else: continue
        taxa, x = wavfile.read(ESC / "audio" / l["filename"])
        x = x.astype(np.float32) / 32768.0
        x = resample_poly(x, 160, 441).astype(np.float32)[:80000]
        xs.append(x); ys.append(y); folds.append(int(l["fold"])); cats.append(cat)
    x, y, fold, cat = np.stack(xs), np.array(ys), np.array(folds), np.array(cats)
    np.savez_compressed(CACHE, x=x, y=y, fold=fold, cat=cat)
    return x, y, fold, cat
