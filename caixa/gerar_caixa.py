"""Gera as peças da caixa do sensor EcoVoz (STL), verifica malha, volumes e colisões.

Peças impressas: corpo, tampa, plataforma, berço do painel, pernas (2 curtas e 2 longas).
Eixos da montagem: X ao longo do comprimento, Y da árvore (-) para fora (+), Z para cima. Origem no centro do corpo, no fundo.
Uso: python3 gerar_caixa.py   (relatório em ./, STLs em ./stl)
"""
import json, math, sys
from pathlib import Path
import numpy as np
import trimesh
from manifold3d import Manifold as M, CrossSection as C, JoinType
import parametros as P

SAIDA = Path(__file__).parent
STL = SAIDA / "stl"
STL.mkdir(exist_ok=True)
D = P.derivados()
L, W, H = D["ext_c"], D["ext_l"], D["alt"]
IL, IW = D["interno_c"], D["interno_l"]
TH = math.radians(P.INCLINACAO)

def rrect(w, h, r, z0, z1):
    cs = C.square((w - 2 * r, h - 2 * r), center=True).offset(r, JoinType.Round, 2.0, 40)
    return M.extrude(cs, z1 - z0).translate((0, 0, z0))

def cil(r, z0, z1, x=0.0, y=0.0, seg=56):
    return M.cylinder(z1 - z0, r, r, seg).translate((x, y, z0))

def cx(r, x0, x1, y=0.0, z=0.0, seg=56):      # cilindro ao longo de X
    return M.cylinder(x1 - x0, r, r, seg).rotate((0, 90, 0)).translate((x0, y, z))

def cy(r, y0, y1, x=0.0, z=0.0, seg=56):      # cilindro ao longo de Y
    return M.cylinder(y1 - y0, r, r, seg).rotate((-90, 0, 0)).translate((x, y0, z))

def cubo(x0, x1, y0, y1, z0, z1):
    return M.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))

# posições das orelhas (centro): quatro nas extremidades curtas, duas na face frontal
ORELHAS = [(sx * (L / 2 + 6.5), sy * 16.0) for sx in (-1, 1) for sy in (-1, 1)] + [(-28.0, W / 2 + 6.5), (28.0, W / 2 + 6.5)]

def orelha(ex, ey, z0, z1):
    r = P.ORELHA_D / 2
    corpo = cil(r, z0, z1, ex, ey)
    if abs(ey) > W / 2:       # orelha da frente: ponte até a parede
        liga = cubo(ex - r, ex + r, W / 2 - 2, ey, z0, z1)
    else:
        sx = 1 if ex > 0 else -1
        liga = cubo(min(ex, sx * (L / 2 - 2)), max(ex, sx * (L / 2 - 2)), ey - r, ey + r, z0, z1)
    return corpo + liga

def corpo():
    c = rrect(L, W, 5, 0, H) - rrect(IL, IW, 2, P.PISO, H + 1)
    for (ex, ey) in ORELHAS:
        c = c + orelha(ex, ey, 0.0, H)
    # apoios da plataforma nas paredes longas
    zl = D["ledge_z"]
    for s in (-1, 1):
        y0, y1 = (IW / 2 - 6, IW / 2 + 0.5) if s > 0 else (-IW / 2 - 0.5, -IW / 2 + 6)
        c = c + cubo(-IL / 2 + 0.5, IL / 2 - 0.5, y0, y1, zl - 3.0, zl)
    # estrutura traseira: placa a 3,5 mm da parede e dois túneis para a cinta
    y_par = -W / 2
    c = c + cubo(-L / 2, L / 2, y_par - P.TUNEL_FOLGA - P.PLACA_TRASEIRA, y_par + 0.5, 0, H)
    t1 = (4.0, 4.0 + P.TUNEL_ALT)
    t2 = (H - 4.0 - P.TUNEL_ALT, H - 4.0)
    for (a, b) in (t1, t2):
        c = c - cubo(-L / 2 - 1, L / 2 + 1, y_par - P.TUNEL_FOLGA, y_par, a, b)
    # furos dos insertos
    for (ex, ey) in ORELHAS:
        c = c - cil(P.INSERTO_D / 2, H - P.INSERTO_P, H + 0.1, ex, ey)
    # SMA na extremidade +X, parte alta; respiro na face +Y; microfone no piso
    c = c - cx(P.SMA_FURO / 2, L / 2 - 5, L / 2 + 1, 0.0, H - 16)
    c = c - cy(P.RESPIRO_FURO / 2, W / 2 - 5, W / 2 + 1, -30.0, 20.0)
    mx, my = 34.0, -24.0
    c = c - cil(P.MIC_MEMBRANA_D / 2, -0.1, P.MIC_MEMBRANA_P, mx, my) - cil(P.MIC_PORTA_D / 2, -0.1, P.PISO + 0.1, mx, my)
    return c

def anel_mic():
    """Anel pinga-água do microfone, colado sob o piso em volta do furo acústico (peça separada, impressa em pé)."""
    d_ext, d_int, alt = P.MIC_ANEL
    return cil(d_ext / 2, 0, alt) - cil(d_int / 2, -1, alt + 1)

def tampa():
    z0, z1 = H, D["tampa_topo"]
    t = rrect(L + 2 * P.TAMPA_ABA, W + 2 * P.TAMPA_ABA, 9, z0, z1)
    for (ex, ey) in ORELHAS:
        t = t + orelha(ex, ey, z0, z1)
    # canaleta do cordão de silicone, na face inferior, centrada na parede
    cl, cw = L - P.PAREDE, W - P.PAREDE
    ext = rrect(cl + P.CANALETA_L, cw + P.CANALETA_L, 3, z0 - 0.1, z0 + P.CANALETA_P)
    inn = rrect(cl - P.CANALETA_L, cw - P.CANALETA_L, 2, z0 - 0.2, z0 + P.CANALETA_P + 0.1)
    t = t - (ext - inn)
    for (ex, ey) in ORELHAS:
        t = t - cil(P.PARAFUSO_FURO / 2, z0 - 0.1, z1 + 0.1, ex, ey)
    # blocos das pernas com insertos (cegos) e passagem do cabo do painel
    for (x, y) in P.PERNA_POS:
        t = t + cil(P.BLOCO_PERNA_D / 2, z1 - 0.1, D["bloco_topo"], x, y)
        t = t - cil(P.INSERTO_D / 2, D["bloco_topo"] - P.INSERTO_P, D["bloco_topo"] + 0.1, x, y)
    t = t - cil(P.PRENSA_CABO_FURO / 2, z0 - 0.1, z1 + 0.1, -17.0, 24.0)
    return t

def plataforma():
    zl = D["ledge_z"]
    p = cubo(-(IL - 2) / 2, (IL - 2) / 2, -(IW - 2) / 2, (IW - 2) / 2, zl, zl + P.PLATAFORMA_ESP)
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = p - cil(P.PLACA_FURO_D / 2, zl - 0.1, zl + P.PLATAFORMA_ESP + 0.1, sx * P.PLACA_FUROS[0] / 2, sy * P.PLACA_FUROS[1] / 2)
    for sx in (-1, 1):   # passagem dos fios entre a bateria e a placa
        p = p - cubo(sx * 40 - 10, sx * 40 + 10, -3, 3, zl - 0.1, zl + P.PLATAFORMA_ESP + 0.1)
    return p

# ---- painel: geometria no sistema local do berço (face de assento em z=0, mais 3 mm de lábio) ----
PW, PD, PT = P.PAINEL
BW, BD = PW + 2 * (P.BERCO_FOLGA_PAINEL / 2 + P.BERCO_LABIO + 1.5), PD + 2 * (P.BERCO_FOLGA_PAINEL / 2 + P.BERCO_LABIO + 1.5)
XC, YC = -42.5, 34.0     # centro do berço em planta (painel deslocado para -X: antena livre no lado +X)

def plano_inferior(y):    # z do plano inferior do berço, no mundo, em função de y
    zf = D["bloco_topo"] + P.PERNA_FRENTE_H
    return zf + (22.0 - y) * math.tan(TH)

def mundo_do_berco():
    """Matriz local -> mundo. Local: z=0 é a face de assento, plano inferior em z=-espessura."""
    yb = YC - P.BERCO_ESP * math.sin(TH)
    zb = plano_inferior(yb) + 0 - 0
    # ponto local (0,0,-esp) vai para (XC, yb, plano(yb))
    # Rx(-th): y' cos + z' sin ; z' cos - y' sin  (ver derivação no relatório)
    T = np.array([XC, yc_mundo(), 0.0])
    return T

def yc_mundo():
    return YC

def berco_local():
    b = cubo(-BW / 2, BW / 2, -BD / 2, BD / 2, -P.BERCO_ESP, 0)
    ext = cubo(-(PW + P.BERCO_FOLGA_PAINEL) / 2 - P.BERCO_LABIO, (PW + P.BERCO_FOLGA_PAINEL) / 2 + P.BERCO_LABIO,
               -(PD + P.BERCO_FOLGA_PAINEL) / 2 - P.BERCO_LABIO, (PD + P.BERCO_FOLGA_PAINEL) / 2 + P.BERCO_LABIO, -0.1, PT)
    inn = cubo(-(PW + P.BERCO_FOLGA_PAINEL) / 2, (PW + P.BERCO_FOLGA_PAINEL) / 2, -(PD + P.BERCO_FOLGA_PAINEL) / 2,
               (PD + P.BERCO_FOLGA_PAINEL) / 2, -0.2, PT + 0.1)
    b = b + (ext - inn)
    # entalhes de drenagem no lábio do lado baixo (+Y local), dois de 10 mm
    for xx in (-40.0, 40.0):
        b = b - cubo(xx - 5, xx + 5, (PD + P.BERCO_FOLGA_PAINEL) / 2 - 0.1, (PD + P.BERCO_FOLGA_PAINEL) / 2 + P.BERCO_LABIO + 0.1, -0.05, PT + 0.1)
    return b

def locais_furos_no_berco():
    """Converte os pontos (x, y) das pernas e do cabo (mundo, planta) em coordenadas locais do berço."""
    out = {}
    c, s = math.cos(TH), math.sin(TH)
    for k, (x, y) in enumerate(P.PERNA_POS):
        out[k] = (x - XC, (y - YC) / c)
    out["cabo"] = (-17.0 - XC, (24.0 - YC) / c)
    return out

def berco_com_furos_local():
    b = berco_local()
    pts = locais_furos_no_berco()
    for k in range(4):
        xl, yl = pts[k]
        b = b - cil(P.PARAFUSO_FURO / 2, -P.BERCO_ESP - 0.1, 0.1, xl, yl) - cil(3.2, -2.2, 0.1, xl, yl)
    xl, yl = pts["cabo"]
    b = b - cil(4.5, -P.BERCO_ESP - 0.1, 0.1, xl, yl)
    return b

def transformar_berco(m):
    """Local -> mundo: gira -THETA em X e translada para que o plano inferior passe nas pontas das pernas.
    Retorna (malha no mundo, deslocamento T) para permitir a transformação inversa."""
    m = m.rotate((-P.INCLINACAO, 0, 0))
    # Rx(-th) leva o ponto local (0,0,-esp) a (0, -esp*sin th, -esp*cos th)
    py, pz = -P.BERCO_ESP * math.sin(TH), -P.BERCO_ESP * math.cos(TH)
    z_alvo = plano_inferior(YC + py)
    T = (XC, YC, z_alvo - pz)
    return m.translate(T), T

def furar_berco_no_mundo(m):
    """Furos verticais (eixo do parafuso): passagem de 3,4 mm, cabeça rebaixada e passagem do cabo do painel."""
    c = 1.0 / math.cos(TH)
    for (x, y) in P.PERNA_POS:
        z_sup = plano_inferior(y) + P.BERCO_ESP * c        # plano de assento acima da perna
        m = m - cil(P.PARAFUSO_FURO / 2, z_sup - 20, z_sup + 20, x, y)
        m = m - cil(3.2, z_sup - 2.2, z_sup + 20, x, y)
    z_cabo = plano_inferior(24.0) + P.BERCO_ESP * c
    m = m - cil(4.5, z_cabo - 20, z_cabo + 20, -17.0, 24.0)
    return m

def berco_para_impressao(m_mundo, T):
    """Mundo -> local (assento para cima, plano na mesa)."""
    return m_mundo.translate((-T[0], -T[1], -T[2])).rotate((P.INCLINACAO, 0, 0)).translate((0, 0, P.BERCO_ESP))

def perna(y_mundo):
    """Perna vertical: base plana no bloco da tampa e topo cortado no plano inclinado do berço."""
    zb = D["bloco_topo"]
    alto = plano_inferior(y_mundo) - zb
    r = P.PERNA_D / 2
    cilind = cil(r, 0, alto + r * math.tan(TH) + 1.0, 0, 0)
    # plano de corte: z = alto + (0 - y) * tan(th)  (y local da perna, rear mais alto)
    cortador = cubo(-20, 20, -20, 20, 0, 80).rotate((-P.INCLINACAO, 0, 0)).translate((0, 0, alto - 40 * 0))
    # constrói o corte por interseção com semiespaço: usa trim_by_plane
    normal = (0.0, math.sin(TH), math.cos(TH))          # normal do plano inferior do berço (aponta para dentro do berço)
    origem_off = alto                                    # offset ao longo de z na origem
    # plano: n . (p - (0,0,alto)) <= 0 mantém o lado abaixo do plano
    n = np.array(normal); 
    # trim_by_plane mantém o lado onde n.p >= offset; usamos a normal oposta
    cil2 = cilind.trim_by_plane((-n[0], -n[1], -n[2]), -float(np.dot(n, np.array([0, 0, alto]))))
    cil2 = cil2 - cil(P.PARAFUSO_FURO / 2, -1, alto + 40)
    return cil2

def para_trimesh(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)

def relatorio_malha(nome, mesh, densidade=1.07, preenchimento=0.55):
    bb = mesh.bounds
    return dict(peca=nome, fechada=bool(mesh.is_watertight), volume_cm3=round(mesh.volume / 1000, 2),
                massa_g_estimada=round(mesh.volume / 1000 * densidade * preenchimento, 1),
                dimensoes_mm=[round(float(v), 1) for v in (bb[1] - bb[0])], componentes=len(mesh.split(only_watertight=False)))

def principal():
    partes = {}
    partes["corpo"] = corpo()
    partes["tampa"] = tampa()
    partes["plataforma"] = plataforma()
    partes["anel_mic"] = anel_mic().translate((34.0, -24.0, -P.MIC_ANEL[2]))
    b_mundo, T = transformar_berco(berco_local())
    b_mundo = furar_berco_no_mundo(b_mundo)
    partes["berco_painel"] = b_mundo
    partes["berco_painel_local"] = berco_para_impressao(b_mundo, T)
    pernas = {}
    for k, (x, y) in enumerate(P.PERNA_POS):
        pernas[k] = perna(y).translate((x, y, D["bloco_topo"]))
        partes[f"perna_{k}"] = pernas[k]
    malhas = {k: para_trimesh(v) for k, v in partes.items()}
    return partes, malhas

if __name__ == "__main__":
    partes, malhas = principal()
    rel = [relatorio_malha(k, v) for k, v in malhas.items()]
    for r in rel:
        print(r)
    (SAIDA / "relatorio_malha.json").write_text(json.dumps(rel, indent=1))
