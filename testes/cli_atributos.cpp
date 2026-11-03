// Lê int16 bruto (16000 amostras) de um arquivo e grava os 31x32 floats de atributos em outro.
#include <stdio.h>
#include <vector>
#include "../nucleo/atributos.hpp"
int main(int argc, char** argv) {
  if (argc < 3) { fprintf(stderr, "uso: %s entrada.pcm saida.f32\n", argv[0]); return 2; }
  FILE* f = fopen(argv[1], "rb"); if (!f) return 3;
  std::vector<int16_t> pcm(ecovoz::JANELA);
  size_t n = fread(pcm.data(), sizeof(int16_t), ecovoz::JANELA, f); fclose(f);
  if (n != (size_t)ecovoz::JANELA) { fprintf(stderr, "arquivo curto\n"); return 4; }
  ecovoz::ExtratorAtributos ex;
  std::vector<float> out(ecovoz::N_QUADROS * ecovoz::N_MELS);
  ex.extrair(pcm.data(), out.data());
  FILE* g = fopen(argv[2], "wb"); fwrite(out.data(), sizeof(float), out.size(), g); fclose(g);
  return 0;
}
