// Carga útil de 12 bytes do alerta EcoVoz e regra de decisão com persistência.
// Portátil e testável no computador. Formato documentado em docs/protocolo_alerta.md.
#pragma once
#include <math.h>
#include <stdint.h>

namespace ecovoz {

enum Classe : uint8_t {
  CL_BATIMENTO = 0,   // mensagem periódica de saúde, sem detecção
  CL_MOTOSSERRA = 1,
  CL_MOTOR = 2,       // trator, caminhão, moto, barco a motor
  CL_FOGO = 3,        // reservado, linha experimental, não usado na fase 1
};

enum Sinais : uint8_t {
  SIN_POSICAO_GNSS = 1 << 0,   // posição obtida por GNSS (senão, posição cadastrada)
  SIN_ATUALIZACAO = 1 << 1,    // evento continua, não é o primeiro aviso
  SIN_BATERIA_BAIXA = 1 << 2,
  SIN_REINICIO = 1 << 3,       // o sensor reiniciou desde o último envio
};

constexpr int TAM_ALERTA = 12;

struct Alerta {
  uint16_t sensor;      // identificador do sensor, 0 a 65535
  double latitude;      // graus decimais
  double longitude;
  uint8_t classe;       // Classe
  uint8_t sinais;       // máscara de Sinais
  uint8_t confianca;    // 0 a 255 representa 0 a 100 %
  uint8_t bateria;      // 0 a 100 %
  uint8_t idade_s;      // segundos entre a primeira detecção e o envio, saturado em 255
};

// Layout (big endian):
//  0-1  sensor
//  2-4  latitude  = round((lat + 90) / 180 * 2^24)    resolução ~1,2 m
//  5-7  longitude = round((lon + 180) / 360 * 2^24)   resolução ~2,4 m no equador
//  8    classe (4 bits altos) | sinais (4 bits baixos)
//  9    confiança
// 10    bateria
// 11    idade do evento em segundos
inline void empacotar(const Alerta& a, uint8_t* out) {
  const double L = 16777216.0;  // 2^24
  double la = (a.latitude + 90.0) / 180.0 * L;
  double lo = (a.longitude + 180.0) / 360.0 * L;
  la = la < 0 ? 0 : (la > L - 1 ? L - 1 : la);
  lo = lo < 0 ? 0 : (lo > L - 1 ? L - 1 : lo);
  const uint32_t ila = static_cast<uint32_t>(lround(la));
  const uint32_t ilo = static_cast<uint32_t>(lround(lo));
  out[0] = a.sensor >> 8; out[1] = a.sensor & 0xFF;
  out[2] = (ila >> 16) & 0xFF; out[3] = (ila >> 8) & 0xFF; out[4] = ila & 0xFF;
  out[5] = (ilo >> 16) & 0xFF; out[6] = (ilo >> 8) & 0xFF; out[7] = ilo & 0xFF;
  out[8] = static_cast<uint8_t>((a.classe & 0x0F) << 4 | (a.sinais & 0x0F));
  out[9] = a.confianca;
  out[10] = a.bateria > 100 ? 100 : a.bateria;
  out[11] = a.idade_s;
}

inline Alerta desempacotar(const uint8_t* in) {
  const double L = 16777216.0;
  Alerta a;
  a.sensor = static_cast<uint16_t>(in[0] << 8 | in[1]);
  const uint32_t ila = static_cast<uint32_t>(in[2]) << 16 | in[3] << 8 | in[4];
  const uint32_t ilo = static_cast<uint32_t>(in[5]) << 16 | in[6] << 8 | in[7];
  a.latitude = ila / L * 180.0 - 90.0;
  a.longitude = ilo / L * 360.0 - 180.0;
  a.classe = in[8] >> 4;
  a.sinais = in[8] & 0x0F;
  a.confianca = in[9];
  a.bateria = in[10];
  a.idade_s = in[11];
  return a;
}

// Regra de decisão: alerta quando pelo menos K das últimas N janelas passam do limiar da classe.
// Depois do alerta, só envia atualização a cada `intervalo_atualizacao_s` enquanto o som persistir.
// O evento termina depois de `silencio_fim_s` sem nenhuma janela positiva.
struct ParametrosDecisao {
  float limiar_motosserra = 0.80f;
  float limiar_motor = 0.90f;
  uint8_t k = 3;
  uint8_t n = 4;
  uint32_t intervalo_atualizacao_s = 300;
  uint32_t silencio_fim_s = 60;
  bool motor_gera_alerta = false;   // fase 1: só motosserra dispara alerta
};

enum class Acao : uint8_t { NENHUMA, ALERTA_NOVO, ATUALIZACAO, FIM_DE_EVENTO };

class Decisor {
 public:
  explicit Decisor(const ParametrosDecisao& p = ParametrosDecisao()) : p_(p) {}

  // prob_*: saídas do modelo (0 a 1). t_s: relógio monotônico em segundos.
  // classe_saida e confianca_saida só valem quando a ação não é NENHUMA.
  Acao atualizar(float prob_motosserra, float prob_motor, uint32_t t_s,
                 uint8_t* classe_saida, float* confianca_saida) {
    const bool pos_motosserra = prob_motosserra >= p_.limiar_motosserra;
    const bool pos_motor = p_.motor_gera_alerta && prob_motor >= p_.limiar_motor;
    const bool positivo = pos_motosserra || pos_motor;
    hist_ = static_cast<uint8_t>(((hist_ << 1) | (positivo ? 1 : 0)) & ((1u << p_.n) - 1u));
    if (positivo) {
      ultimo_positivo_s_ = t_s;
      if (pos_motosserra) { classe_atual_ = CL_MOTOSSERRA; conf_atual_ = prob_motosserra; }
      else { classe_atual_ = CL_MOTOR; conf_atual_ = prob_motor; }
    }
    int soma = 0;
    for (int i = 0; i < p_.n; ++i) soma += (hist_ >> i) & 1;
    *classe_saida = classe_atual_;
    *confianca_saida = conf_atual_;

    if (!em_evento_) {
      if (soma >= p_.k) {
        em_evento_ = true;
        inicio_evento_s_ = t_s;
        ultimo_envio_s_ = t_s;
        return Acao::ALERTA_NOVO;
      }
      return Acao::NENHUMA;
    }
    if (t_s - ultimo_positivo_s_ >= p_.silencio_fim_s) {
      em_evento_ = false; hist_ = 0;
      return Acao::FIM_DE_EVENTO;
    }
    if (positivo && t_s - ultimo_envio_s_ >= p_.intervalo_atualizacao_s) {
      ultimo_envio_s_ = t_s;
      return Acao::ATUALIZACAO;
    }
    return Acao::NENHUMA;
  }

  uint32_t idade_evento_s(uint32_t t_s) const { return em_evento_ ? t_s - inicio_evento_s_ : 0; }
  bool em_evento() const { return em_evento_; }

 private:
  ParametrosDecisao p_;
  uint8_t hist_ = 0;
  bool em_evento_ = false;
  uint32_t inicio_evento_s_ = 0, ultimo_envio_s_ = 0, ultimo_positivo_s_ = 0;
  uint8_t classe_atual_ = CL_MOTOSSERRA;
  float conf_atual_ = 0.0f;
};

}  // namespace ecovoz
