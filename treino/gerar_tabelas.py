"""Gera nucleo/tabelas_atributos.h (janela de Hann e banco mel esparso) a partir de atributos.py."""
from pathlib import Path
import numpy as np
import atributos as A

def principal(destino):
    hann = A.janela_hann()
    mel = A.banco_mel()
    linhas = []
    linhas.append("// Arquivo gerado por treino/gerar_tabelas.py. Não edite à mão.")
    linhas.append("#pragma once")
    linhas.append("#include <stdint.h>")
    linhas.append("namespace ecovoz {")
    linhas.append(f"constexpr int TAXA_HZ = {A.TAXA_HZ};")
    linhas.append(f"constexpr int JANELA = {A.JANELA};")
    linhas.append(f"constexpr int QUADRO = {A.QUADRO};")
    linhas.append(f"constexpr int PASSO = {A.PASSO};")
    linhas.append(f"constexpr int N_FFT = {A.N_FFT};")
    linhas.append(f"constexpr int N_BINS = {A.N_BINS};")
    linhas.append(f"constexpr int N_MELS = {A.N_MELS};")
    linhas.append(f"constexpr int N_QUADROS = {A.N_QUADROS};")
    linhas.append(f"constexpr float PISO_LOG = {A.PISO_LOG:.1e}f;")
    linhas.append("static const float HANN[QUADRO] = {")
    linhas.append(",".join(f"{v:.9e}f" for v in hann) + "};")
    inicio, tam, pesos = [], [], []
    for m in range(A.N_MELS):
        nz = np.nonzero(mel[m])[0]
        inicio.append(int(nz[0])); tam.append(int(len(nz)))
        pesos.extend(float(v) for v in mel[m, nz[0]:nz[-1] + 1])
    linhas.append(f"static const uint16_t MEL_INICIO[N_MELS] = {{{','.join(map(str, inicio))}}};")
    linhas.append(f"static const uint16_t MEL_TAMANHO[N_MELS] = {{{','.join(map(str, tam))}}};")
    # recalcula tamanhos como o trecho contíguo completo (inclui zeros internos, se houver)
    linhas.append(f"static const float MEL_PESOS[{len(pesos)}] = {{")
    linhas.append(",".join(f"{v:.9e}f" for v in pesos) + "};")
    linhas.append("}  // namespace ecovoz")
    Path(destino).write_text("\n".join(linhas) + "\n")
    print("gravado", destino, f"({len(pesos)} pesos mel)")

if __name__ == "__main__":
    import sys
    principal(sys.argv[1] if len(sys.argv) > 1 else "../nucleo/tabelas_atributos.h")
