"""Gera desenho_tecnico.svg (3 vistas cotadas) a partir dos mesmos parâmetros das peças."""
import math
import parametros as P
D = P.derivados()
import gerar_caixa as G
_, _m = G.principal()
ZMAX = max(m.bounds[1][2] for k, m in _m.items() if k != 'berco_painel_local')
L, W, H = D["ext_c"], D["ext_l"], D["alt"]
IL, IW = D["interno_c"], D["interno_l"]
TH = math.radians(P.INCLINACAO)
S = 2.5
XC, YC = -42.5, 34.0
PW, PD, PT = P.PAINEL
BW = PW + 2 * (P.BERCO_FOLGA_PAINEL / 2 + P.BERCO_LABIO + 1.5)
BD = PD + 2 * (P.BERCO_FOLGA_PAINEL / 2 + P.BERCO_LABIO + 1.5)
out = []
def a(s): out.append(s)
def f(v): return f"{v:.1f}"
TXT = "font-family='DejaVu Sans, Arial, sans-serif'"

class Vista:
    def __init__(s, ox, oy, h_up=True): s.ox, s.oy, s.up = ox, oy, h_up
    def X(s, x): return s.ox + x * S
    def Y(s, y): return s.oy - y * S if s.up else s.oy + y * S

def retangulo(v, x0, x1, y0, y1, cls="p", extra=""):
    xa, xb = sorted((v.X(x0), v.X(x1))); ya, yb = sorted((v.Y(y0), v.Y(y1)))
    a(f"<rect x='{f(xa)}' y='{f(ya)}' width='{f(xb-xa)}' height='{f(yb-ya)}' class='{cls}' {extra}/>")

def linha(v, x0, y0, x1, y1, cls="p"):
    a(f"<line x1='{f(v.X(x0))}' y1='{f(v.Y(y0))}' x2='{f(v.X(x1))}' y2='{f(v.Y(y1))}' class='{cls}'/>")

def texto(px, py, t, size=12, anchor="middle", weight="400", fill="#111", rot=0):
    tr = f" transform='rotate({rot} {f(px)} {f(py)})'" if rot else ""
    a(f"<text x='{f(px)}' y='{f(py)}' font-size='{size}' text-anchor='{anchor}' font-weight='{weight}' fill='{fill}' {TXT}{tr}>{t}</text>")

def cota_h(v, x0, x1, y, rotulo, desloc=18):
    py = v.Y(y) + desloc
    for x in (x0, x1):
        a(f"<line x1='{f(v.X(x))}' y1='{f(v.Y(y)+ (3 if desloc>0 else -3))}' x2='{f(v.X(x))}' y2='{f(py + (4 if desloc>0 else -4))}' class='c'/>")
    a(f"<line x1='{f(v.X(x0))}' y1='{f(py)}' x2='{f(v.X(x1))}' y2='{f(py)}' class='c' marker-start='url(#seta)' marker-end='url(#seta)'/>")
    texto((v.X(x0) + v.X(x1)) / 2, py - 4, rotulo, 11)

def cota_v(v, x, y0, y1, rotulo, desloc=-18):
    px = v.X(x) + desloc
    for y in (y0, y1):
        a(f"<line x1='{f(v.X(x) + (-3 if desloc<0 else 3))}' y1='{f(v.Y(y))}' x2='{f(px + (-4 if desloc<0 else 4))}' y2='{f(v.Y(y))}' class='c'/>")
    a(f"<line x1='{f(px)}' y1='{f(v.Y(y0))}' x2='{f(px)}' y2='{f(v.Y(y1))}' class='c' marker-start='url(#seta)' marker-end='url(#seta)'/>")
    texto(px - 4, (v.Y(y0) + v.Y(y1)) / 2, rotulo, 11, rot=-90)

W_SVG, H_SVG = 1500, 1120
a(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W_SVG} {H_SVG}' width='{W_SVG}' height='{H_SVG}'>")
a("""<defs><marker id='seta' viewBox='0 0 10 10' refX='5' refY='5' markerWidth='6' markerHeight='6' orient='auto-start-reverse'><path d='M0 0L10 5L0 10z' fill='#444'/></marker></defs>
<style>.p{fill:none;stroke:#111;stroke-width:1.6}.f{fill:#e9efec;stroke:#111;stroke-width:1.6}.t{fill:none;stroke:#111;stroke-width:1;stroke-dasharray:6 3}
.c{stroke:#444;stroke-width:.9;fill:none}.g{fill:#f4f4f4;stroke:#888;stroke-width:1}.az{fill:#cfd8e6;stroke:#26466d;stroke-width:1.4}.e{stroke:#888;stroke-width:.6;stroke-dasharray:14 3 2 3;fill:none}</style>
<rect width='100%' height='100%' fill='#fff'/>""")
texto(30, 38, "EcoVoz: caixa do sensor, fase 1 (protótipo)", 22, "start", "700")
texto(30, 60, "Medidas em milímetros. Peças impressas em ASA (ou PETG) com parede de 4 mm. Valores [CONFERIR] dependem da peça comprada.", 12, "start", fill="#444")

# ---------- Vista frontal (X-Z), projeção ----------
v = Vista(400, 480)
texto(v.X(0), 100, "Vista frontal (X-Z)", 15, weight="700")
retangulo(v, -L/2, L/2, 0, H, "f")
retangulo(v, -IL/2, IL/2, P.PISO, H, "p", "fill='#fff'")
retangulo(v, -P.SUPORTE_BATERIA[0]/2, P.SUPORTE_BATERIA[0]/2, P.PISO, P.PISO+P.SUPORTE_BATERIA[2], "t")
retangulo(v, -(IL-2)/2, (IL-2)/2, D["ledge_z"], D["ledge_z"]+P.PLATAFORMA_ESP, "g")
zp0 = D["ledge_z"] + P.PLATAFORMA_ESP + P.ESPACADOR
retangulo(v, -P.PLACA[0]/2, P.PLACA[0]/2, zp0, zp0 + P.PLACA[2], "t")
retangulo(v, -P.PLACA[0]/2, P.PLACA[0]/2, D["topo_placa"], D["topo_placa"] + P.ALTURA_COMPONENTES, "t")
retangulo(v, -(L/2+P.TAMPA_ABA), L/2+P.TAMPA_ABA, H, D["tampa_topo"], "f")
# pernas e berço (projeção)
zf = D["bloco_topo"] + P.PERNA_FRENTE_H
zr = zf + 44 * math.tan(TH)
for x in (-35, 32):
    retangulo(v, x - P.BLOCO_PERNA_D/2, x + P.BLOCO_PERNA_D/2, D["tampa_topo"], D["bloco_topo"], "f")
    retangulo(v, x - P.PERNA_D/2, x + P.PERNA_D/2, D["bloco_topo"], zr - 2, "g")
retangulo(v, XC - BW/2, XC + BW/2, zf - 3.5, zr + 8, "az", "fill-opacity='.55'")
texto(v.X(XC), v.Y(zr + 8) - 8, f"painel {PW:.0f} x {PD:.0f} mm, inclinado {P.INCLINACAO:.0f} graus", 11)
# antena
linha(v, L/2 + 2, H - 16, L/2 + 2, H + 70, "p")
texto(v.X(L/2 + 2) + 10, v.Y(H + 70), "antena (haste vertical)", 11, "start")
cota_v(v, -L/2, 0, H, f"{H:.1f}", -22)
cota_v(v, -L/2, H, D["tampa_topo"], f"{P.TAMPA_ESP:.0f}", -48)
cota_v(v, L/2 + 4, 0, D["bloco_topo"], f"{D['bloco_topo']:.1f}", 70)
cota_h(v, -L/2, L/2, 0, f"{L:.0f}", 22)
cota_h(v, -IL/2, IL/2, 0, f"cavidade {IL:.0f}", 44)
cota_h(v, -(L/2+P.TAMPA_ABA), L/2+P.TAMPA_ABA, 0, f"tampa {L+2*P.TAMPA_ABA:.0f}", 66)
texto(v.X(-IL/2 + 3), v.Y(P.PISO + 18), "suporte 26650", 10, "start", fill="#555")
texto(v.X(-IL/2 + 3), v.Y(D["topo_placa"] + 6), "placa e rádio", 10, "start", fill="#555")

# ---------- Vista superior (X-Y) ----------
v2 = Vista(1130, 420)
texto(v2.X(-40) - 10, 100, "Vista superior (X-Y)", 15, weight="700")
retangulo(v2, XC - BW/2, XC + BW/2, YC - BD/2, YC + BD/2, "az", "fill-opacity='.4'")
retangulo(v2, XC - PW/2, XC + PW/2, YC - PD/2, YC + PD/2, "az", "fill-opacity='.6'")
rx = lambda r: r * S
a(f"<rect x='{f(v2.X(-L/2-P.TAMPA_ABA))}' y='{f(v2.Y(W/2+P.TAMPA_ABA))}' width='{f((L+2*P.TAMPA_ABA)*S)}' height='{f((W+2*P.TAMPA_ABA)*S)}' rx='{f(9*S)}' class='f' fill-opacity='.85'/>")
retangulo(v2, -L/2, L/2, -W/2, W/2, "p")
retangulo(v2, -L/2, L/2, -W/2 - P.TUNEL_FOLGA - P.PLACA_TRASEIRA, -W/2 - P.TUNEL_FOLGA, "f")
for (ex, ey) in [(sx * (L/2 + 6.5), sy * 16.0) for sx in (-1, 1) for sy in (-1, 1)] + [(-28.0, W/2+6.5), (28.0, W/2+6.5)]:
    a(f"<circle cx='{f(v2.X(ex))}' cy='{f(v2.Y(ey))}' r='{f(P.ORELHA_D/2*S)}' class='p'/><circle cx='{f(v2.X(ex))}' cy='{f(v2.Y(ey))}' r='{f(P.PARAFUSO_FURO/2*S)}' class='p'/>")
for (x, y) in P.PERNA_POS:
    a(f"<circle cx='{f(v2.X(x))}' cy='{f(v2.Y(y))}' r='{f(P.PERNA_D/2*S)}' class='t'/>")
a(f"<circle cx='{f(v2.X(-17))}' cy='{f(v2.Y(24))}' r='{f(P.PRENSA_CABO_FURO/2*S)}' class='p'/>")
texto(v2.X(-17), v2.Y(24) - 22, "prensa-cabo PG7", 10)
texto(v2.X(L/2) + 6, v2.Y(0) - 8, "SMA", 10, "start")
texto(v2.X(0), v2.Y(-W/2 - 12), "face traseira (tronco)", 11)
cota_h(v2, -L/2, L/2, -W/2 - 7.5, f"{L:.0f}", 38)
cota_h(v2, XC - BW/2, XC + BW/2, YC + BD/2, f"berço {BW:.0f}", -16)
cota_v(v2, XC - BW/2, YC - BD/2, YC + BD/2, f"{BD:.0f}", -22)
cota_v(v2, L/2 + 4, -W/2, W/2, f"{W:.0f}", 70)
texto(v2.X(L/2) + 8, v2.Y(-W/2) + 56, f"antena (SMA) a {L/2 - (XC + PW/2):.0f} mm da borda do painel", 10, "start", fill="#a33")

# ---------- Vista lateral (Y-Z) ----------
v3 = Vista(250, 1010)
texto(v3.X(5), 640, "Vista lateral (Y-Z)", 15, weight="700")
linha(v3, -W/2 - 7.5, -5, -W/2 - 7.5, H + 60, "e")
texto(v3.X(-W/2 - 7.5) - 6, v3.Y(H + 60) - 8, "tronco", 11, "end")
retangulo(v3, -W/2, W/2, 0, H, "f")
retangulo(v3, -IW/2, IW/2, P.PISO, H, "p", "fill='#fff'")
retangulo(v3, -W/2 - P.TUNEL_FOLGA - P.PLACA_TRASEIRA, -W/2 - P.TUNEL_FOLGA, 0, H, "f")
for (z0, z1) in ((4, 4 + P.TUNEL_ALT), (H - 4 - P.TUNEL_ALT, H - 4)):
    retangulo(v3, -W/2 - P.TUNEL_FOLGA, -W/2, z0, z1, "p", "fill='#fff3d6'")
retangulo(v3, -(W/2+P.TAMPA_ABA), W/2+P.TAMPA_ABA, H, D["tampa_topo"], "f")
# berço inclinado como paralelogramo
ya, yb = YC - BD/2*math.cos(TH), YC + BD/2*math.cos(TH)
za = zf + (22 - ya) * math.tan(TH); zb = zf + (22 - yb) * math.tan(TH)
a(f"<polygon points='{f(v3.X(ya))},{f(v3.Y(za))} {f(v3.X(yb))},{f(v3.Y(zb))} {f(v3.X(yb))},{f(v3.Y(zb+P.BERCO_ESP+PT))} {f(v3.X(ya))},{f(v3.Y(za+P.BERCO_ESP+PT))}' class='az'/>")
for (x, y) in P.PERNA_POS:
    if x > 0:
        zt = zf + (22 - y) * math.tan(TH)
        retangulo(v3, y - P.PERNA_D/2, y + P.PERNA_D/2, D["bloco_topo"], zt, "g")
        retangulo(v3, y - P.BLOCO_PERNA_D/2, y + P.BLOCO_PERNA_D/2, D["tampa_topo"], D["bloco_topo"], "f")
cota_v(v3, -W/2 - 7.5, 0, H, f"{H:.1f}", -24)
cota_h(v3, -W/2 - 7.5, W/2, 0, f"{W + 7.5:.1f} com a placa traseira", 22)
cota_v(v3, W/2 + P.TAMPA_ABA, 4, 4 + P.TUNEL_ALT, f"túnel {P.TUNEL_ALT:.0f}", 26)
cota_h(v3, -W/2 - P.TUNEL_FOLGA - P.PLACA_TRASEIRA, -W/2 - P.TUNEL_FOLGA, H + 12, f"{P.PLACA_TRASEIRA:.0f}", -16)
texto(v3.X(-W/2 - 5.5), v3.Y(15) + 4, "fita", 9, "middle", fill="#8a5a00", rot=-90)
texto(v3.X(-W/2 - 7.5), v3.Y(zr + 24), f"inclinação {P.INCLINACAO:.0f} graus, lado alto junto ao tronco", 11, "start")

# ---------- Quadro de dimensões ----------
qx, qy = 780, 700
texto(qx, qy, "Dimensões principais", 15, "start", "700")
linhas = [
 ("Corpo, externo (C x L x A)", f"{L:.0f} x {W:.0f} x {H:.1f}"),
 ("Cavidade interna (C x L x A)", f"{IL:.0f} x {IW:.0f} x {H - P.PISO:.1f}"),
 ("Parede, piso, tampa", f"{P.PAREDE:.0f}, {P.PISO:.0f}, {P.TAMPA_ESP:.0f}"),
 ("Tampa (com aba de 4 mm)", f"{L + 2*P.TAMPA_ABA:.0f} x {W + 2*P.TAMPA_ABA:.0f} x {P.TAMPA_ESP:.0f}"),
 ("Altura total, até o lábio traseiro do berço", f"{ZMAX:.0f}"),
 ("Berço do painel", f"{BW:.0f} x {BD:.0f} x {P.BERCO_ESP + PT:.0f}"),
 ("Painel solar (conferir)", f"{PW:.0f} x {PD:.0f} x {PT:.0f}"),
 ("Cordão de silicone / canaleta", f"{P.CORDAO:.0f} / {P.CANALETA_L} x {P.CANALETA_P}"),
 ("Parafusos da tampa", "6 x M3 x 12 + inserto M3"),
 ("Cinta de fixação", f"{P.FITA_LARGURA:.0f} mm, 2 túneis de {P.TUNEL_ALT:.0f} x {P.TUNEL_FOLGA}"),
 ("Furos: SMA / PG7 / respiro / mic", f"{P.SMA_FURO} / {P.PRENSA_CABO_FURO} / {P.RESPIRO_FURO} / {P.MIC_PORTA_D}"),
]
for i, (k, val) in enumerate(linhas):
    y = qy + 26 + i * 22
    a(f"<line x1='{qx}' y1='{y + 6}' x2='{qx + 640}' y2='{y + 6}' stroke='#ddd'/>")
    texto(qx, y, k, 12, "start"); texto(qx + 640, y, val, 12, "end", "600")
a("</svg>")
from pathlib import Path
Path(__file__).parent.joinpath("desenho_tecnico.svg").write_text("\n".join(out), encoding="utf-8")
print("desenho_tecnico.svg gravado")
