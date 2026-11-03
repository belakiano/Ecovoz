"""Compara receitas de treino usando APENAS o fold de validação (o fold de teste não é tocado)."""
import sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
import tensorflow as tf
from sklearn.metrics import roc_auc_score
import treinar as T, atributos as A, dados_esc50 as D

x, y, fold, cat = D.carregar()
teste, val = 5, 1
rng = np.random.default_rng(100 + teste)
tr = ~np.isin(fold, [teste, val])
pcm_tr, y_tr = T.montar_treino(x[tr], y[tr], rng)
raw_tr = T.atributos_brutos(pcm_tr)
pcm_va, y_va, snr_va, _ = T.montar_avaliacao(x[fold == val], y[fold == val], rng)
raw_va = T.atributos_brutos(pcm_va)
print("treino", raw_tr.shape, np.bincount(y_tr), "| validação", raw_va.shape, flush=True)

def prep(r, nivel):
    if nivel: r = r - r.mean(axis=(1, 2), keepdims=True)   # invariância ao ganho do microfone
    return r

def aumentar(X, rg, freq=4, tempo=6):
    X = X.copy(); n = len(X)
    for i in range(n):
        f = rg.integers(0, freq + 1); f0 = rg.integers(0, A.N_MELS - f + 1); X[i, :, f0:f0 + f] = 0
        t = rg.integers(0, tempo + 1); t0 = rg.integers(0, A.N_QUADROS - t + 1); X[i, t0:t0 + t, :] = 0
        X[i] = np.roll(X[i], rg.integers(-6, 7), axis=0)
    return X

def auc_serra(prob, y, snr, s):
    m = (snr == s) | ((snr == 99) & (y == 0)) | ((snr == 99) & (y == 2))
    # positivos: motosserra no SNR s; negativos: ambiente e motor limpos
    mm = ((snr == s) & (y == 1)) | ((snr == 99) & (y != 1))
    return roc_auc_score((y[mm] == 1).astype(int), prob[mm, 1])

def rodar(nome, nivel, aug, epocas=30, largura=1.0, semente=1):
    tf.keras.utils.set_random_seed(semente)
    mu = prep(raw_tr, nivel).mean(); sd = prep(raw_tr, nivel).std()
    Xtr = ((prep(raw_tr, nivel) - mu) / sd).astype(np.float32)[..., None]
    Xva = ((prep(raw_va, nivel) - mu) / sd).astype(np.float32)[..., None]
    m = T.construir_modelo()
    m.compile(tf.keras.optimizers.Adam(2e-3), "sparse_categorical_crossentropy")
    cont = np.bincount(y_tr, minlength=3); pesos = {i: float(len(y_tr) / (3 * cont[i])) for i in range(3)}
    rg = np.random.default_rng(5); melhor = (0, None, -1); t0 = time.time()
    for ep in range(epocas):
        Xe = aumentar(Xtr[..., 0], rg)[..., None] if aug else Xtr
        m.fit(Xe, y_tr, epochs=1, batch_size=64, class_weight=pesos, verbose=0)
        if ep % 3 == 2 or ep == epocas - 1:
            p = m.predict(Xva, verbose=0, batch_size=256)
            a = {s: auc_serra(p, y_va, snr_va, s) for s in (99, 10, 0)}
            media = np.mean(list(a.values()))
            if media > melhor[0]: melhor = (media, a, ep + 1)
    print(f"{nome:34s} melhor AUC média {melhor[0]:.3f} na época {melhor[2]:2d} | AUC limpo {melhor[1][99]:.3f} 10dB {melhor[1][10]:.3f} 0dB {melhor[1][0]:.3f} | {time.time()-t0:.0f}s", flush=True)

rodar("V0 base", False, False)
rodar("V1 sem nível por janela", True, False)
rodar("V2 sem nível + máscaras/rolagem", True, True)
rodar("V3 só máscaras/rolagem", False, True)
