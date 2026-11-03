#!/usr/bin/env python3
"""Orçamento de energia e dimensionamento solar do sensor EcoVoz.

Todas as correntes são premissas de ordem de grandeza tiradas de folhas de
dados típicas. Meça no protótipo (analisador de corrente) e atualize os
valores em PREMISSAS antes de decidir painel e bateria.
"""
import math

PREMISSAS = {
    # ciclo de escuta
    "ciclo_s": 3.0,            # período entre janelas
    "ativo_s": 1.15,           # aquecimento do microfone + captura de 1 s + inferência
    "i_ativo_mA": 28.0,        # MCU a 80 MHz com espera, microfone e regulador
    "i_sono_mA": 0.6,          # sono leve do MCU + regulador + rádio dormindo
    # rádio (SX1262 a +22 dBm)
    "i_tx_mA": 120.0,
    "i_rx_mA": 30.0,           # MCU ativo + rádio recebendo
    "rx_s": 0.5,               # janelas de recepção após cada envio
    # rotina de envios
    "eventos_por_dia": 20,
    "envios_por_evento": 13,   # 1 alerta + atualização a cada 5 min durante 1 h
    "batimento_cardiaco_h": 6, # mensagem de saúde a cada 6 h
    # alimentação
    "tensao_servico_V": 3.3,
    "eficiencia_regulador": 0.90,
    "eficiencia_carregador": 0.85,
    # bateria LiFePO4 26650
    "bateria_mAh": 3000,
    "bateria_V": 3.2,
    "profundidade_uso": 0.80,
    # painel
    "painel_W": 3.0,
    "fator_orientacao": 0.70,  # painel fixo, sem rastreio, com sujeira
}

def tempo_no_ar_lora(payload_bytes, sf, bw_hz=125_000, cr=1, preambulo=8,
                     cabecalho_explicito=True, crc=True):
    """Tempo no ar de um quadro LoRa (fórmula do manual do SX126x)."""
    de = 1 if (sf >= 11 and bw_hz == 125_000) else 0
    ih = 0 if cabecalho_explicito else 1
    tsym = (2 ** sf) / bw_hz
    num = 8 * payload_bytes - 4 * sf + 28 + 16 * (1 if crc else 0) - 20 * ih
    n_carga = 8 + max(math.ceil(num / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (preambulo + 4.25) * tsym + n_carga * tsym

def calcular(p=PREMISSAS, sf=10):
    # LoRaWAN soma 13 bytes de cabeçalho e MIC ao payload do aplicativo
    t_tx = tempo_no_ar_lora(12 + 13, sf)
    q_tx_As = p["i_tx_mA"] / 1000 * t_tx + p["i_rx_mA"] / 1000 * p["rx_s"]  # A·s por envio

    sono_s = p["ciclo_s"] - p["ativo_s"]
    i_escuta = (p["ativo_s"] * p["i_ativo_mA"] + sono_s * p["i_sono_mA"]) / p["ciclo_s"]

    envios_dia = p["eventos_por_dia"] * p["envios_por_evento"] + 24 / p["batimento_cardiaco_h"]
    i_radio = envios_dia * q_tx_As * 1000 / 86400  # mA médios

    i_medio = i_escuta + i_radio
    e_dia_carga_Wh = i_medio / 1000 * p["tensao_servico_V"] * 24
    e_dia_bateria_Wh = e_dia_carga_Wh / p["eficiencia_regulador"]
    e_dia_painel_Wh = e_dia_bateria_Wh / p["eficiencia_carregador"]

    cap_Wh = p["bateria_mAh"] / 1000 * p["bateria_V"]
    autonomia_dias = cap_Wh * p["profundidade_uso"] / e_dia_bateria_Wh
    return {
        "tempo_no_ar_s": t_tx, "q_envio_mAs": q_tx_As * 1000,
        "i_escuta_mA": i_escuta, "i_radio_mA": i_radio, "i_medio_mA": i_medio,
        "e_dia_carga_Wh": e_dia_carga_Wh, "e_dia_bateria_Wh": e_dia_bateria_Wh,
        "e_dia_painel_Wh": e_dia_painel_Wh, "capacidade_Wh": cap_Wh,
        "autonomia_dias": autonomia_dias,
    }

def producao_painel_Wh(hsp, fator_sombra, p=PREMISSAS):
    return p["painel_W"] * hsp * p["fator_orientacao"] * fator_sombra

if __name__ == "__main__":
    r = calcular()
    print("== Tempo no ar de 12 B (+13 B de LoRaWAN) em AU915, 125 kHz ==")
    for sf in (7, 8, 9, 10):
        print(f"  SF{sf}: {tempo_no_ar_lora(25, sf)*1000:6.0f} ms")
    print("\n== Orçamento médio ==")
    for k, v in r.items():
        print(f"  {k:20s} {v:8.3f}")
    need = r["e_dia_painel_Wh"]
    print(f"\n== Produção do painel de {PREMISSAS['painel_W']} W contra necessidade de {need:.2f} Wh/dia ==")
    for hsp, nome in ((5.0, "seca"), (4.0, "chuvosa")):
        for sombra in (1.0, 0.3, 0.2, 0.1):
            prod = producao_painel_Wh(hsp, sombra)
            print(f"  HSP {hsp} ({nome:7s}) luz {int(sombra*100):3d}%: {prod:5.2f} Wh/dia  margem x{prod/need:4.1f}")
    for hsp in (5.0, 4.0, 3.0):
        s_min = need / (PREMISSAS['painel_W'] * hsp * PREMISSAS['fator_orientacao'])
        print(f"  luz mínima para fechar o balanço com HSP {hsp}: {s_min*100:.0f}% do sol aberto")
    # PDF original: bateria 2000 mAh Li-ion 3,7 V a 15 mA contínuos
    dias_pdf = 2.0 * 3.7 / (0.015 * 3.3 * 24 / 0.9) * 0.8
    print(f"\nPDF original: 2000 mAh a 15 mA contínuos dura {dias_pdf:.1f} dias sem sol")
    # malha hexagonal
    for d in (400, 500, 600):
        area_km2 = math.sqrt(3) / 2 * (d / 1000) ** 2
        print(f"  espaçamento {d} m: {area_km2:.3f} km² por sensor, {10/area_km2:.0f} sensores para 1000 ha")
