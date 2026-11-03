"""Parâmetros da caixa do sensor EcoVoz (fase 1). Todas as medidas em milímetros.

Os valores marcados com [CONFERIR] dependem do modelo exato comprado. Meça a peça física com
paquímetro antes de imprimir e ajuste aqui: peças, desenho técnico, lista de materiais e relatório
são regerados a partir deste arquivo (python3 gerar_caixa.py).
"""
import math

# ---- componentes internos ----
BATERIA_DIAMETRO = 26.5          # LiFePO4 26650
SUPORTE_BATERIA = (80.0, 33.0, 33.0)   # [CONFERIR] suporte 1x26650 (comprimento, largura, altura)
PLACA = (90.0, 56.0, 1.6)        # placa-mãe de protótipo (comprimento, largura, espessura)
PLACA_FUROS = (82.0, 48.0)       # distância entre furos de fixação
PLACA_FURO_D = 3.2
ESPACADOR = 6.0                  # espaçador M3 entre plataforma e placa
ALTURA_COMPONENTES = 12.0        # maior componente sobre a placa (soquete, módulo de rádio)
MIC_PLACA = (14.0, 14.0, 1.6)    # [CONFERIR] placa do microfone MEMS I2S
# ---- paredes, folgas ----
PAREDE = 4.0                     # ASA, 6 perímetros de 0,4 mm
PISO = 3.0
FOLGA = 1.5
TAMPA_ESP = 5.0
TAMPA_ABA = 4.0                  # a tampa avança 4 mm além da parede (pinga-água e cobre a canaleta)
PLATAFORMA_ESP = 3.0
# ---- vedação ----
CORDAO = 3.0                     # cordão de silicone redondo de 3 mm
CANALETA_L = 3.4
CANALETA_P = 2.2
INSERTO_D = 4.2                  # inserto de latão M3 a quente
INSERTO_P = 6.0
ORELHA_D = 12.0
ORELHA_ALT = 6.0
PARAFUSO_FURO = 3.4
# ---- aberturas ----
MIC_PORTA_D = 3.0
MIC_MEMBRANA_D = 9.0
MIC_MEMBRANA_P = 1.2
MIC_ANEL = (18.0, 14.0, 5.0)     # anel pinga-água sob o piso: diâmetro externo, interno, altura
SMA_FURO = 6.6                   # SMA fêmea de painel [CONFERIR]
PRENSA_CABO_FURO = 12.5          # PG7
RESPIRO_FURO = 12.2              # respiro M12x1,5 com membrana de ePTFE
# ---- fixação ----
FITA_LARGURA = 20.0              # cinta de nylon de 20 mm com fivela de came
TUNEL_ALT = 22.0
TUNEL_FOLGA = 3.5
PLACA_TRASEIRA = 4.0
# ---- painel solar ----
PAINEL = (160.0, 138.0, 3.0)     # [CONFERIR] 6 V / 3 W, largura x profundidade x espessura
INCLINACAO = 12.0
PERNA_D = 12.0
PERNA_FRENTE_H = 18.0            # altura das pernas dianteiras acima do bloco da tampa
BLOCO_PERNA_D = 10.0
BLOCO_PERNA_H = 4.0
PERNA_POS = ((-35.0, -22.0), (32.0, -22.0), (-35.0, 22.0), (32.0, 22.0))   # (x, y) no centro da tampa
BERCO_ESP = 4.0
BERCO_FOLGA_PAINEL = 1.0
BERCO_LABIO = 2.0

def derivados():
    sc, sl, sh = SUPORTE_BATERIA
    interno_c = max(sc, PLACA[0]) + 2 * FOLGA + 6.0
    interno_l = max(sl, PLACA[1]) + 2 * FOLGA + 4.0
    ledge_z = PISO + sh + 2.0                         # topo do apoio da plataforma
    topo_placa = ledge_z + PLATAFORMA_ESP + ESPACADOR + PLACA[2]
    alt = topo_placa + ALTURA_COMPONENTES + FOLGA    # altura da parede (até o plano da tampa)
    ext_c, ext_l = interno_c + 2 * PAREDE, interno_l + 2 * PAREDE
    tampa_topo = alt + TAMPA_ESP
    bloco_topo = tampa_topo + BLOCO_PERNA_H
    th = math.tan(math.radians(INCLINACAO))
    return dict(interno_c=interno_c, interno_l=interno_l, interno_h=alt - PISO, ledge_z=ledge_z,
                topo_placa=topo_placa, alt=alt, ext_c=ext_c, ext_l=ext_l, tampa_topo=tampa_topo,
                bloco_topo=bloco_topo, tg=th)

if __name__ == "__main__":
    for k, v in derivados().items():
        print(f"{k:12s} {v:8.2f}")
