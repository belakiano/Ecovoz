"""Treino, quantização int8 e avaliação do classificador acústico do EcoVoz (3 classes).

Uso:
  python3 treinar.py --cv             validação cruzada em 5 folds (estimativa do desempenho)
  python3 treinar.py --final          treina o modelo final e grava os arquivos de exportação

Todo número que sai daqui vale só para os dados usados (ESC-50) e NÃO representa desempenho em campo.
"""
import argparse, json, math, os, sys, time
from pathlib import Path
import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf
import atributos as A
import dados_esc50 as D

SAIDA = Path(__file__).resolve().parent / "resultados"
SNRS = [20, 10, 5, 0, -5]
LIMIARES = [0.5, 0.7, 0.8, 0.9, 0.95]

# ---------- sinais ----------
def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12)

def misturar(sinal, fundo, snr_db):
    g = rms(sinal) / (rms(fundo) * 10 ** (snr_db / 20))
    return sinal + fundo * g

def a_pcm(x):
    return np.clip(np.round(x * 32768), -32768, 32767).astype(np.int16)

def janelas(clipe, passo):
    out = []
    for i in range(0, clipe.shape[0] - A.JANELA + 1, passo):
        w = clipe[i:i + A.JANELA]
        if np.abs(w).max() >= 1e-4:      # descarta silêncio digital de preenchimento
            out.append(w)
    return out

def ruido_microfone(rng):
    nivel_db = rng.uniform(-75, -55)
    return rng.standard_normal(A.JANELA).astype(np.float32) * 10 ** (nivel_db / 20)

# ---------- montagem dos conjuntos ----------
def montar_treino(x, y, rng, n_aug=6):
    amb = [w for c in x[y == 0] for w in janelas(c, 8000)]
    exemplos, rotulos = [], []
    for cl in (1, 2):
        for c in x[y == cl]:
            for w in janelas(c, 4000):
                for _ in range(n_aug):
                    s = w.copy()
                    if rng.random() < 0.85:
                        s = misturar(s, amb[rng.integers(len(amb))], rng.uniform(-5, 25))
                    s = s * 10 ** (rng.uniform(-15, 5) / 20) + ruido_microfone(rng)
                    exemplos.append(a_pcm(s)); rotulos.append(cl)
    for w in amb:
        for k in range(2):
            s = w.copy()
            if k == 1:
                s = misturar(s, amb[rng.integers(len(amb))], rng.uniform(-5, 10))
            s = s * 10 ** (rng.uniform(-15, 5) / 20) + ruido_microfone(rng)
            exemplos.append(a_pcm(s)); rotulos.append(0)
    return np.stack(exemplos), np.array(rotulos)

def montar_avaliacao(x, y, rng):
    """Conjunto limpo + positivos misturados a fundo de floresta em SNRs fixos."""
    amb = [w for c in x[y == 0] for w in janelas(c, 8000)]
    ex, rot, snr, clipe = [], [], [], []
    for i, (c, cl) in enumerate(zip(x, y)):
        for w in janelas(c, 8000):
            ex.append(a_pcm(w)); rot.append(cl); snr.append(99); clipe.append(i)
            if cl in (1, 2):
                for s in SNRS:
                    m = misturar(w, amb[rng.integers(len(amb))], s)
                    ex.append(a_pcm(m)); rot.append(cl); snr.append(s); clipe.append(i)
    return np.stack(ex), np.array(rot), np.array(snr), np.array(clipe)

def atributos_brutos(pcm):
    return np.stack([A.log_mel_bruto(p) for p in pcm])

# ---------- modelo ----------
def construir_modelo(largura=1.0):
    L = tf.keras.layers
    f = lambda n: max(8, int(round(n * largura)))
    ent = tf.keras.Input((A.N_QUADROS, A.N_MELS, 1), name="log_mel")
    x = L.Conv2D(f(16), 3, strides=2, padding="same", use_bias=False)(ent)
    x = L.BatchNormalization()(x); x = L.ReLU()(x)
    for filtros, passo in ((32, 1), (48, 2), (64, 2), (64, 1)):
        x = L.DepthwiseConv2D(3, strides=passo, padding="same", use_bias=False)(x)
        x = L.BatchNormalization()(x); x = L.ReLU()(x)
        x = L.Conv2D(f(filtros), 1, use_bias=False)(x)
        x = L.BatchNormalization()(x); x = L.ReLU()(x)
    x = L.GlobalAveragePooling2D()(x)
    x = L.Dropout(0.2)(x)
    sai = L.Dense(3, activation="softmax", name="classes")(x)
    return tf.keras.Model(ent, sai)

def aumentar_espectro(X, rg, freq=4, tempo=6):
    """Máscaras de frequência e de tempo e rolagem temporal (estilo SpecAugment). X: (n, 31, 32)."""
    X = X.copy()
    for i in range(len(X)):
        f = rg.integers(0, freq + 1); f0 = rg.integers(0, A.N_MELS - f + 1); X[i, :, f0:f0 + f] = 0
        t = rg.integers(0, tempo + 1); t0 = rg.integers(0, A.N_QUADROS - t + 1); X[i, t0:t0 + t, :] = 0
        X[i] = np.roll(X[i], rg.integers(-6, 7), axis=0)
    return X

def auc_serra(prob, y, snr, s):
    from sklearn.metrics import roc_auc_score
    mm = ((snr == s) & (y == 1)) | ((snr == 99) & (y != 1))
    return roc_auc_score((y[mm] == 1).astype(int), prob[mm, 1])

def treinar_modelo(Xtr, ytr, Xva, yva, snr_va, epocas=45, semente=1, largura=1.0):
    """Treina com aumento espectral por época. Escolhe a época pela AUC média de validação
    (limpo, 10 dB, 0 dB), não pela perda, porque a perda pune a calibração e não o ranqueamento."""
    tf.keras.utils.set_random_seed(semente)
    m = construir_modelo(largura)
    m.compile(tf.keras.optimizers.Adam(2e-3), "sparse_categorical_crossentropy")
    cont = np.bincount(ytr, minlength=3)
    pesos = {i: float(len(ytr) / (3 * cont[i])) for i in range(3)}
    rg = np.random.default_rng(5 + semente)
    melhor, pesos_melhores, ep_melhor = -1.0, None, 0
    for ep in range(epocas):
        m.fit(aumentar_espectro(Xtr[..., 0], rg)[..., None], ytr, epochs=1, batch_size=64, class_weight=pesos, verbose=0)
        if ep % 3 == 2 or ep == epocas - 1:
            p = m.predict(Xva, verbose=0, batch_size=256)
            a = float(np.mean([auc_serra(p, yva, snr_va, s) for s in (99, 10, 0)]))
            if a > melhor:
                melhor, pesos_melhores, ep_melhor = a, m.get_weights(), ep + 1
    m.set_weights(pesos_melhores)
    return m, ep_melhor, melhor

def converter_int8(m, Xrep):
    conv = tf.lite.TFLiteConverter.from_keras_model(m)
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    def rep():
        for i in range(len(Xrep)):
            yield [Xrep[i:i + 1].astype(np.float32)]
    conv.representative_dataset = rep
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8
    conv.inference_output_type = tf.int8
    return conv.convert()

def prever_tflite(modelo_bytes, X):
    it = tf.lite.Interpreter(model_content=modelo_bytes)
    it.allocate_tensors()
    ent, sai = it.get_input_details()[0], it.get_output_details()[0]
    es, ez = ent["quantization"]; ss, sz = sai["quantization"]
    out = np.zeros((len(X), 3), np.float32)
    for i in range(len(X)):
        q = np.clip(np.round(X[i] / es + ez), -128, 127).astype(np.int8)[None]
        it.set_tensor(ent["index"], q); it.invoke()
        out[i] = (it.get_tensor(sai["index"])[0].astype(np.float32) - sz) * ss
    return out

# ---------- métricas ----------
def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)

def metricas(prob, y, snr, clipe):
    r = {}
    limpo = snr == 99
    pred = prob.argmax(1)
    cm = np.zeros((3, 3), int)
    for t, p in zip(y[limpo], pred[limpo]): cm[t, p] += 1
    r["matriz_confusao_limpo"] = cm.tolist()
    r["recall_por_classe_limpo"] = [float(cm[i, i] / max(cm[i].sum(), 1)) for i in range(3)]
    r["precisao_por_classe_limpo"] = [float(cm[i, i] / max(cm[:, i].sum(), 1)) for i in range(3)]
    r["alerta_motosserra"] = {}
    for T in LIMIARES:
        pos = prob[:, 1] >= T
        d = {"limiar": T}
        m = limpo & (y == 1); d["recall_limpo"] = float(pos[m].mean()) if m.any() else None
        d["recall_por_snr"] = {}
        for s in SNRS:
            m = (snr == s) & (y == 1); d["recall_por_snr"][str(s)] = float(pos[m].mean()) if m.any() else None
        m = limpo & (y == 0); k = int(pos[m].sum()); n = int(m.sum())
        d["falso_positivo_ambiente"] = k / n; d["ic95_fp_ambiente"] = wilson(k, n); d["n_janelas_ambiente"] = n
        m = limpo & (y == 2); k = int(pos[m].sum()); n = int(m.sum())
        d["motor_confundido_com_motosserra"] = k / max(n, 1)
        r["alerta_motosserra"][str(T)] = d
    r["n_clipes_motosserra"] = int(len(set(clipe[limpo & (y == 1)])))
    r["n_clipes_motor"] = int(len(set(clipe[limpo & (y == 2)])))
    r["n_clipes_ambiente"] = int(len(set(clipe[limpo & (y == 0)])))
    return r

def uma_dobra(x, y, fold, teste, val, semente=1, devolver_modelo=False, largura=1.0):
    rng = np.random.default_rng(100 + teste)
    tr = ~np.isin(fold, [teste, val])
    pcm_tr, y_tr = montar_treino(x[tr], y[tr], rng)
    raw_tr = atributos_brutos(pcm_tr)
    mu, sd = float(raw_tr.mean()), float(raw_tr.std())
    norm = lambda r: ((r - mu) / sd).astype(np.float32)[..., None]
    pcm_va, y_va, snr_va, _ = montar_avaliacao(x[fold == val], y[fold == val], rng)
    Xva = norm(atributos_brutos(pcm_va))
    t0 = time.time()
    m, ep, auc_va = treinar_modelo(norm(raw_tr), y_tr, Xva, y_va, snr_va, semente=semente, largura=largura)
    pcm_te, y_te, snr_te, clipe_te = montar_avaliacao(x[fold == teste], y[fold == teste], rng)
    Xte = norm(atributos_brutos(pcm_te))
    prob_f = m.predict(Xte, verbose=0, batch_size=256)
    idx = rng.choice(len(raw_tr), 400, replace=False)
    tfl = converter_int8(m, norm(raw_tr)[idx])
    prob_q = prever_tflite(tfl, Xte)
    res = {"fold_teste": teste, "fold_validacao": val, "melhor_epoca": ep, "auc_validacao": auc_va, "largura": largura, "mu": mu, "sd": sd,
           "n_treino": int(len(y_tr)), "segundos_treino": round(time.time() - t0, 1),
           "float": metricas(prob_f, y_te, snr_te, clipe_te), "int8": metricas(prob_q, y_te, snr_te, clipe_te),
           "tamanho_tflite_bytes": len(tfl), "parametros": int(m.count_params())}
    return (res, m, tfl, mu, sd) if devolver_modelo else res

def resumo_cv(res, chave="int8", T="0.8"):
    linhas = []
    for r in res:
        d = r[chave]["alerta_motosserra"][T]
        linhas.append((r["fold_teste"], d["recall_limpo"], d["recall_por_snr"], d["falso_positivo_ambiente"], d["motor_confundido_com_motosserra"]))
    return linhas

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", action="store_true"); ap.add_argument("--final", action="store_true")
    ap.add_argument("--largura", type=float, default=1.0); ap.add_argument("--dobras", type=int, nargs="*", default=[1, 2, 3, 4, 5])
    a = ap.parse_args()
    x, y, fold, cat = D.carregar()
    if a.cv:
        arq = SAIDA / f"metricas_cv_larg{a.largura}.json"
        res = json.loads(arq.read_text()) if arq.exists() else []
        res = [r for r in res if r["fold_teste"] not in a.dobras]
        for f in a.dobras:
            r = uma_dobra(x, y, fold, f, f % 5 + 1, largura=a.largura)
            res.append(r); res.sort(key=lambda q: q["fold_teste"])
            d = r["int8"]["alerta_motosserra"]["0.8"]
            print(f"fold {f}: época {r['melhor_epoca']} treino {r['segundos_treino']}s | int8 T=0.8 recall limpo {d['recall_limpo']:.3f} "
                  f"FP ambiente {d['falso_positivo_ambiente']:.4f} motor->serra {d['motor_confundido_com_motosserra']:.3f} "
                  f"| TFLite {r['tamanho_tflite_bytes']/1024:.1f} KB, {r['parametros']} parâmetros", flush=True)
            (SAIDA / f"metricas_cv_larg{a.largura}.json").write_text(json.dumps(res, indent=1))
    if a.final:
        r, m, tfl, mu, sd = uma_dobra(x, y, fold, 5, 1, devolver_modelo=True, largura=a.largura)
        (SAIDA / "modelo_ecovoz_int8.tflite").write_bytes(tfl)
        m.save(SAIDA / "modelo_ecovoz_float.keras")
        (Path(__file__).parent / "normalizacao.json").write_text(json.dumps({"media": mu, "desvio": sd}))
        (SAIDA / "metricas_final.json").write_text(json.dumps(r, indent=1))
        print("modelo final gravado; TFLite", len(tfl), "bytes; média/desvio", mu, sd)
