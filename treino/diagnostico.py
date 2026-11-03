import numpy as np, time, warnings
warnings.filterwarnings("ignore")
import treinar as T, atributos as A, dados_esc50 as D

x, y, fold, cat = D.carregar()
teste, val = 5, 1
rng = np.random.default_rng(100 + teste)
tr = ~np.isin(fold, [teste, val])
pcm_tr, y_tr = T.montar_treino(x[tr], y[tr], rng)
raw_tr = T.atributos_brutos(pcm_tr); mu, sd = raw_tr.mean(), raw_tr.std()
n = lambda r: ((r - mu) / sd).astype(np.float32)
pcm_te, y_te, snr_te, clipe_te = T.montar_avaliacao(x[fold == teste], y[fold == teste], rng)
raw_te = T.atributos_brutos(pcm_te)
# 1) referência simples: média e desvio no tempo de cada banda mel -> regressão logística
def resumo(r): 
    z = n(r); return np.concatenate([z.mean(1), z.std(1)], axis=1)
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
for nome, clf in (("logística", LogisticRegression(max_iter=2000, class_weight="balanced")),
                  ("floresta aleatória", RandomForestClassifier(200, n_jobs=-1, class_weight="balanced", random_state=0))):
    clf.fit(resumo(raw_tr), y_tr)
    p = clf.predict_proba(resumo(raw_te)); limpo = snr_te == 99
    cm = np.zeros((3,3),int)
    for t, q in zip(y_te[limpo], p[limpo].argmax(1)): cm[t,q]+=1
    print(nome, "matriz limpo:", cm.tolist(), "recall serra", round(cm[1,1]/cm[1].sum(),3), "precisão serra", round(cm[1,1]/cm[:,1].sum(),3))
    print("   recall serra por SNR (argmax):", {s: round(float((p[snr_te==s].argmax(1)[y_te[snr_te==s]==1]==1).mean()),2) for s in T.SNRS})
# 2) quais categorias de ambiente viram motosserra (CNN já treinada em resultados? treina de novo rápido)
Xtr = n(raw_tr)[..., None]
pcm_va, y_va, _, _ = T.montar_avaliacao(x[fold == val], y[fold == val], rng)
Xva = n(T.atributos_brutos(pcm_va))[..., None]
m, ep = T.treinar_modelo(Xtr, y_tr, Xva, y_va)
pt = m.predict(Xtr, verbose=0, batch_size=256).argmax(1)
print("CNN, acurácia de TREINO por classe:", [round(float((pt[y_tr==c]==c).mean()),3) for c in range(3)], "época", ep)
Xte = n(raw_te)[..., None]; pr = m.predict(Xte, verbose=0, batch_size=256)
limpo = snr_te == 99
cats_te = cat[fold == teste]
import collections
fp = collections.Counter(); tot = collections.Counter()
for p_, yy, ci in zip(pr[limpo], y_te[limpo], clipe_te[limpo]):
    if yy == 0:
        tot[cats_te[ci]] += 1; fp[cats_te[ci]] += int(p_[1] >= 0.5)
print("FP motosserra (T=0.5) por categoria de ambiente:", {k: f"{fp[k]}/{tot[k]}" for k in sorted(tot) if fp[k] > 0})
