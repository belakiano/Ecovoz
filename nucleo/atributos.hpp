// Extração de atributos log-mel do EcoVoz. Equivalente exato de treino/atributos.py.
// Portátil: não depende de ESP-IDF nem de Arduino. Usa apenas a biblioteca padrão.
#pragma once
#include <math.h>
#include <stdint.h>
#include "tabelas_atributos.h"
#include "normalizacao.h"

namespace ecovoz {

class ExtratorAtributos {
 public:
  ExtratorAtributos() {
    // twiddles da FFT em double, convertidos para float
    for (int k = 0; k < N_FFT / 2; ++k) {
      const double ang = -2.0 * M_PI * k / N_FFT;
      cos_[k] = static_cast<float>(cos(ang));
      sin_[k] = static_cast<float>(sin(ang));
    }
    // tabela de inversão de bits
    int bits = 0;
    while ((1 << bits) < N_FFT) ++bits;
    for (int i = 0; i < N_FFT; ++i) {
      int r = 0;
      for (int b = 0; b < bits; ++b) if (i & (1 << b)) r |= 1 << (bits - 1 - b);
      rev_[i] = static_cast<uint16_t>(r);
    }
  }

  // pcm: JANELA amostras int16. saida: N_QUADROS * N_MELS floats, ordem (quadro, mel), já normalizados.
  void extrair(const int16_t* pcm, float* saida) {
    for (int q = 0; q < N_QUADROS; ++q) {
      const int16_t* p = pcm + q * PASSO;
      // amostras em float e remoção de DC
      float soma = 0.0f;
      for (int n = 0; n < QUADRO; ++n) {
        re_[n] = static_cast<float>(p[n]) * (1.0f / 32768.0f);
        soma += re_[n];
      }
      const float media = soma / static_cast<float>(QUADRO);
      for (int n = 0; n < QUADRO; ++n) re_[n] = (re_[n] - media) * HANN[n];
      for (int n = 0; n < N_FFT; ++n) im_[n] = 0.0f;
      fft();
      for (int k = 0; k < N_BINS; ++k) pot_[k] = re_[k] * re_[k] + im_[k] * im_[k];
      int ofs = 0;
      for (int m = 0; m < N_MELS; ++m) {
        float acc = 0.0f;
        const int ini = MEL_INICIO[m], tam = MEL_TAMANHO[m];
        for (int j = 0; j < tam; ++j) acc += MEL_PESOS[ofs + j] * pot_[ini + j];
        ofs += tam;
        saida[q * N_MELS + m] = (logf(acc + PISO_LOG) - NORM_MEDIA) / NORM_DESVIO;
      }
    }
  }

  // Converte para o tipo de entrada do modelo TFLite int8 (escala e ponto zero vêm do modelo).
  static void quantizar(const float* x, int8_t* y, int n, float escala, int ponto_zero) {
    for (int i = 0; i < n; ++i) {
      float v = x[i] / escala + static_cast<float>(ponto_zero);
      long r = lroundf(v);
      if (r > 127) r = 127;
      if (r < -128) r = -128;
      y[i] = static_cast<int8_t>(r);
    }
  }

 private:
  void fft() {
    // reordena
    for (int i = 0; i < N_FFT; ++i) {
      const int j = rev_[i];
      if (j > i) {
        float t = re_[i]; re_[i] = re_[j]; re_[j] = t;
        t = im_[i]; im_[i] = im_[j]; im_[j] = t;
      }
    }
    for (int tam = 2; tam <= N_FFT; tam <<= 1) {
      const int meio = tam >> 1, passo = N_FFT / tam;
      for (int ini = 0; ini < N_FFT; ini += tam) {
        for (int k = 0; k < meio; ++k) {
          const float wr = cos_[k * passo], wi = sin_[k * passo];
          const int a = ini + k, b = a + meio;
          const float tr = re_[b] * wr - im_[b] * wi;
          const float ti = re_[b] * wi + im_[b] * wr;
          re_[b] = re_[a] - tr; im_[b] = im_[a] - ti;
          re_[a] += tr;         im_[a] += ti;
        }
      }
    }
  }

  float re_[N_FFT], im_[N_FFT], pot_[N_BINS], cos_[N_FFT / 2], sin_[N_FFT / 2];
  uint16_t rev_[N_FFT];
};

}  // namespace ecovoz
