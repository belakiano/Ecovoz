"""Exporta o modelo final para o firmware: modelo_dados.h (modelo TFLite, escalas, operações) e nucleo/normalizacao.h."""
import json, sys
from pathlib import Path
import numpy as np
import tensorflow as tf

RAIZ = Path(__file__).resolve().parent.parent
RES = RAIZ / "treino" / "resultados"

def principal():
    tfl = (RES / "modelo_ecovoz_int8.tflite").read_bytes()
    norm = json.loads((RAIZ / "treino" / "normalizacao.json").read_text())
    it = tf.lite.Interpreter(model_content=tfl, experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES); it.allocate_tensors()
    ent, sai = it.get_input_details()[0], it.get_output_details()[0]
    ops = sorted({d["op_name"] for d in it._get_ops_details()})
    mapa = {"CONV_2D": "AddConv2D", "DEPTHWISE_CONV_2D": "AddDepthwiseConv2D", "MEAN": "AddMean",
            "FULLY_CONNECTED": "AddFullyConnected", "SOFTMAX": "AddSoftmax", "RESHAPE": "AddReshape",
            "QUANTIZE": "AddQuantize", "DEQUANTIZE": "AddDequantize", "ADD": "AddAdd", "MUL": "AddMul",
            "AVERAGE_POOL_2D": "AddAveragePool2D", "PAD": "AddPad"}
    faltam = [o for o in ops if o not in mapa]
    if faltam: sys.exit(f"operações sem mapeamento para o TFLM: {faltam}")
    es, ez = ent["quantization"]; ss, sz = sai["quantization"]
    linhas = ["// Gerado por treino/exportar.py. Não edite à mão.", "#pragma once", "#include <stdint.h>",
              f"constexpr float MODELO_ENTRADA_ESCALA = {es:.9e}f;", f"constexpr int MODELO_ENTRADA_ZP = {int(ez)};",
              f"constexpr float MODELO_SAIDA_ESCALA = {ss:.9e}f;", f"constexpr int MODELO_SAIDA_ZP = {int(sz)};",
              f"#define OPS_DO_MODELO_N {len(ops)}",
              "#define OPS_DO_MODELO_ADICIONAR(r) do { " + " ".join(f"(r).{mapa[o]}();" for o in ops) + " } while (0)",
              f"// operações do modelo: {', '.join(ops)}",
              f"constexpr unsigned int MODELO_TFLITE_TAM = {len(tfl)};",
              "alignas(16) static const unsigned char modelo_tflite[] = {"]
    for i in range(0, len(tfl), 16):
        linhas.append("  " + ",".join(f"0x{b:02x}" for b in tfl[i:i + 16]) + ",")
    linhas.append("};")
    (RAIZ / "firmware" / "src" / "modelo_dados.h").write_text("\n".join(linhas) + "\n")
    (RAIZ / "nucleo" / "normalizacao.h").write_text(
        "// Gerado por treino/exportar.py. Não edite à mão.\n#pragma once\nnamespace ecovoz {\n"
        f"constexpr float NORM_MEDIA = {norm['media']:.9e}f;\nconstexpr float NORM_DESVIO = {norm['desvio']:.9e}f;\n}}\n")
    print(f"modelo {len(tfl)} bytes | operações {ops} | entrada escala {es:.6f} zp {ez} | saída escala {ss:.6f} zp {sz}")

if __name__ == "__main__":
    principal()
