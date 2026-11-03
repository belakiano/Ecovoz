"""Extração de atributos de áudio do EcoVoz (espectrograma log-mel).

Este módulo é a referência. O mesmo cálculo existe em C++ em
nucleo/atributos.hpp e o teste de paridade (testes/teste_paridade.py)
confere que os dois produzem a mesma saída. Qualquer mudança aqui exige
regenerar nucleo/tabelas_atributos.h com treino/gerar_tabelas.py.

Fluxo: janela de 1 s a 16 kHz -> 31 quadros de 512 amostras (passo 500)
-> remoção de DC por quadro -> janela de Hann -> FFT real de 512 pontos
-> potência -> 32 filtros mel triangulares (50 Hz a 8 kHz) -> ln(x+1e-8)
-> normalização global (média e desvio gravados em normalizacao.json).
"""
import json
import math
from pathlib import Path

import numpy as np

TAXA_HZ = 16000
JANELA = 16000          # 1 s
QUADRO = 512            # 32 ms
PASSO = 500             # 31,25 ms
N_FFT = 512
N_BINS = N_FFT // 2 + 1
N_MELS = 32
F_MIN = 50.0
F_MAX = 8000.0
PISO_LOG = 1e-8      # abaixo do ruído de quantização de 16 bits (~1e-8 por filtro mel)
N_QUADROS = 1 + (JANELA - QUADRO) // PASSO   # 31

RAIZ = Path(__file__).resolve().parent.parent
ARQ_NORMALIZACAO = RAIZ / "treino" / "normalizacao.json"


def hz_para_mel(f):
    return 2595.0 * np.log10(1.0 + np.asarray(f, dtype=np.float64) / 700.0)


def mel_para_hz(m):
    return 700.0 * (10.0 ** (np.asarray(m, dtype=np.float64) / 2595.0) - 1.0)


def janela_hann():
    n = np.arange(QUADRO, dtype=np.float64)
    return (0.5 - 0.5 * np.cos(2.0 * math.pi * n / QUADRO)).astype(np.float32)


def banco_mel():
    """Matriz (N_MELS, N_BINS) de triângulos com pico 1, em float32."""
    freq_bins = np.arange(N_BINS, dtype=np.float64) * TAXA_HZ / N_FFT
    pontos = mel_para_hz(np.linspace(hz_para_mel(F_MIN), hz_para_mel(F_MAX), N_MELS + 2))
    banco = np.zeros((N_MELS, N_BINS), dtype=np.float64)
    for m in range(N_MELS):
        esq, cen, dir_ = pontos[m], pontos[m + 1], pontos[m + 2]
        sobe = (freq_bins - esq) / (cen - esq)
        desce = (dir_ - freq_bins) / (dir_ - cen)
        banco[m] = np.maximum(0.0, np.minimum(sobe, desce))
    return banco.astype(np.float32)


_HANN = janela_hann()
_MEL = banco_mel()


def carregar_normalizacao():
    if ARQ_NORMALIZACAO.exists():
        d = json.loads(ARQ_NORMALIZACAO.read_text())
        return float(d["media"]), float(d["desvio"])
    return 0.0, 1.0


def log_mel_bruto(pcm):
    """pcm: vetor de 16000 amostras (int16 ou float em [-1, 1]). Retorna (31, 32) em ln, sem normalizar."""
    x = np.asarray(pcm)
    if x.dtype.kind in "iu":
        x = x.astype(np.float32) / 32768.0
    else:
        x = x.astype(np.float32)
    if x.shape[-1] != JANELA:
        raise ValueError(f"a janela precisa ter {JANELA} amostras")
    idx = np.arange(N_QUADROS)[:, None] * PASSO + np.arange(QUADRO)[None, :]
    q = x[idx]                                   # (31, 512)
    q = q - q.mean(axis=1, keepdims=True)        # remove DC por quadro
    q = q * _HANN[None, :]
    esp = np.fft.rfft(q.astype(np.float32), n=N_FFT, axis=1)
    pot = (esp.real.astype(np.float32) ** 2 + esp.imag.astype(np.float32) ** 2)
    mel = pot @ _MEL.T                           # (31, 32)
    return np.log(mel + np.float32(PISO_LOG)).astype(np.float32)


def extrair(pcm, media=None, desvio=None):
    if media is None or desvio is None:
        media, desvio = carregar_normalizacao()
    return ((log_mel_bruto(pcm) - np.float32(media)) / np.float32(desvio)).astype(np.float32)


def extrair_lote(janelas, media=None, desvio=None):
    return np.stack([extrair(j, media, desvio) for j in janelas])[..., None]
