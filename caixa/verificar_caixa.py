"""Verificações de montagem: colisões, folgas e encaixe dos componentes. Grava os STL de impressão."""
import json
import numpy as np, trimesh
import parametros as P
import gerar_caixa as G
from manifold3d import Manifold as M

partes, malhas = G.principal()
D = G.D
res = {}

def vol(a, b): return float((partes[a] ^ partes[b]).volume())
pares = [("corpo", "tampa"), ("corpo", "plataforma"), ("corpo", "anel_mic"), ("tampa", "berco_painel")] + [("tampa", f"perna_{k}") for k in range(4)] + [("berco_painel", f"perna_{k}") for k in range(4)]
print("interpenetração entre peças (mm3, esperado ~0):")
for a, b in pares:
    v = vol(a, b); res[f"{a}x{b}"] = round(v, 3); print(f"  {a:10s} x {b:12s} {v:8.3f}")

# componentes fantasma dentro da cavidade
cav = G.rrect(G.IL, G.IW, 2, P.PISO, G.H)
fant = {
 "suporte_bateria": G.cubo(-P.SUPORTE_BATERIA[0]/2, P.SUPORTE_BATERIA[0]/2, -P.SUPORTE_BATERIA[1]/2, P.SUPORTE_BATERIA[1]/2, P.PISO, P.PISO+P.SUPORTE_BATERIA[2]),
 "placa_mae": G.cubo(-P.PLACA[0]/2, P.PLACA[0]/2, -P.PLACA[1]/2, P.PLACA[1]/2, D["ledge_z"]+P.PLATAFORMA_ESP+P.ESPACADOR, D["topo_placa"]),
 "componentes_sobre_placa": G.cubo(-P.PLACA[0]/2, P.PLACA[0]/2, -P.PLACA[1]/2, P.PLACA[1]/2, D["topo_placa"], D["topo_placa"]+P.ALTURA_COMPONENTES),
 "microfone": G.cubo(34-7, 34+7, -24-7, -24+7, P.PISO, P.PISO+P.MIC_PLACA[2]+3),
}
print("componentes dentro da cavidade (parte fora, mm3, esperado 0) e contra o corpo (colisão):")
for n, f in fant.items():
    fora = float((f - cav).volume()); col = float((f ^ partes["corpo"]).volume())
    print(f"  {n:24s} fora {fora:7.3f}  colisão com corpo {col:7.3f}")
    res[f"fantasma_{n}"] = (round(fora, 3), round(col, 3))
col_plat = float((fant["placa_mae"] ^ partes["plataforma"]).volume()); print("  placa x plataforma (assenta nos espaçadores, esperado 0):", round(col_plat, 3))
col_tampa = float((fant["componentes_sobre_placa"] ^ partes["tampa"]).volume()); print("  componentes x tampa (esperado 0):", round(col_tampa, 3))
folga_tampa = G.H - (D["topo_placa"] + P.ALTURA_COMPONENTES); print(f"  folga vertical sob a tampa: {folga_tampa:.2f} mm")
folga_bat = D["ledge_z"] - (P.PISO + P.SUPORTE_BATERIA[2]); print(f"  folga entre o suporte da bateria e a plataforma: {folga_bat:.2f} mm")
folga_sma = (G.IL/2) - (P.SUPORTE_BATERIA[0]/2); print(f"  espaço lateral entre suporte da bateria e parede curta: {folga_sma:.2f} mm")

# conectividade da montagem painel: berço + pernas + tampa formam um sólido? (encostam, não interpenetram: usa distância)
bm = malhas["berco_painel"]
for k in range(4):
    pm = malhas[f"perna_{k}"]
    topo = pm.vertices[pm.vertices[:, 2] > pm.vertices[:, 2].max() - 6]
    dist = trimesh.proximity.closest_point(bm, topo)[1]
    print(f"  perna_{k}: distância do topo ao berço  mín {dist.min():.3f} mm  máx {dist.max():.3f} mm")
    res[f"perna_{k}_dist_max"] = round(float(dist.max()), 3)

# antena: distância horizontal entre o SMA (x = L/2, topo da parede) e a borda do painel
x_borda_painel = G.XC + G.PW/2
print(f"  borda +X do painel em x={x_borda_painel:.1f} mm; SMA em x={G.L/2:.1f} mm -> antena a {G.L/2 - x_borda_painel:.1f} mm da borda do painel")
# recuo traseiro: borda traseira do painel contra a face do tronco (y = -W/2 - 7.5)
tronco_y = -G.W/2 - P.TUNEL_FOLGA - P.PLACA_TRASEIRA
borda_tras = G.YC - G.PD/2
print(f"  face de contato com o tronco em y={tronco_y:.1f}; borda traseira do painel em y={borda_tras:.1f} (folga {borda_tras - tronco_y:.1f} mm)")
# altura total e balanço
zmax = max(m.bounds[1][2] for m in malhas.values()); print(f"  altura total da montagem (sem painel nem antena): {zmax:.1f} mm")

# exporta STL de impressão
saida = G.SAIDA
stl = G.STL
imp = {"corpo": malhas["corpo"], "tampa": malhas["tampa"], "plataforma": malhas["plataforma"], "anel_microfone": G.para_trimesh(G.anel_mic())}
imp["berco_painel"] = malhas["berco_painel_local"]   # assento para cima, plano na mesa
for k in (0, 2):
    pm = malhas[f"perna_{k}"].copy(); pm.apply_translation([-pm.bounds[0][0] - 6, -pm.bounds[0][1] - 6, -pm.bounds[0][2]])
    imp[f"perna_{'traseira' if k == 0 else 'dianteira'}"] = pm
for n, m in imp.items():
    m.export(stl / f"{n}.stl")
montagem = trimesh.util.concatenate([malhas[k] for k in malhas if k != "berco_painel_local"])
montagem.export(stl / "montagem_completa.stl")
json.dump(res, open(saida / "verificacoes.json", "w"), indent=1)
print("STL gravados:", sorted(p.name for p in stl.glob("*.stl")))
