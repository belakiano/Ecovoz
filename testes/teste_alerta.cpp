// Testes do empacotador de 12 bytes e do decisor. Modos:
//   teste_alerta decisor            roda os cenários da regra de decisão
//   teste_alerta empacotar          lê linhas "sensor lat lon classe sinais confianca bateria idade" e imprime hex
//   teste_alerta desempacotar       lê linhas com 24 dígitos hex e imprime os campos
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../nucleo/alerta.hpp"
using namespace ecovoz;

static int falhas = 0;
#define VERIFICA(cond, msg) do { if (!(cond)) { printf("FALHA: %s (linha %d)\n", msg, __LINE__); ++falhas; } } while (0)

static Acao passo(Decisor& d, float serra, float motor, uint32_t t, uint8_t* c = nullptr, float* conf = nullptr) {
  uint8_t cc; float ff; Acao a = d.atualizar(serra, motor, t, c ? c : &cc, conf ? conf : &ff); return a;
}

static void cenarios() {
  { // 1. silêncio nunca alerta
    Decisor d; for (uint32_t t = 0; t < 300; t += 3) VERIFICA(passo(d, 0.05f, 0.02f, t) == Acao::NENHUMA, "silêncio não pode alertar");
  }
  { // 2. dois positivos entre negativos não bastam (K=3 de N=4)
    Decisor d; Acao a;
    a = passo(d, 0.9f, 0, 0); VERIFICA(a == Acao::NENHUMA, "1 positivo");
    a = passo(d, 0.1f, 0, 3); a = passo(d, 0.9f, 0, 6); VERIFICA(a == Acao::NENHUMA, "2 positivos de 3");
    a = passo(d, 0.1f, 0, 9); VERIFICA(a == Acao::NENHUMA, "2 positivos de 4");
  }
  { // 3. três de quatro dispara na terceira positiva; idade e classe corretas
    Decisor d; uint8_t c; float conf;
    passo(d, 0.9f, 0, 100); passo(d, 0.1f, 0, 103);
    Acao a = passo(d, 0.95f, 0, 106); VERIFICA(a == Acao::NENHUMA, "só 2 positivos");
    a = passo(d, 0.97f, 0, 109, &c, &conf);
    VERIFICA(a == Acao::ALERTA_NOVO, "deve alertar no 3º positivo");
    VERIFICA(c == CL_MOTOSSERRA && conf > 0.96f, "classe e confiança");
    VERIFICA(d.idade_evento_s(109) == 0 && d.idade_evento_s(121) == 12, "idade do evento");
  }
  { // 4. som contínuo por 12 min: 1 alerta + atualizações a cada 300 s
    Decisor d; int novos = 0, atual = 0; uint32_t t_novo = 0;
    for (uint32_t t = 0; t <= 720; t += 3) {
      Acao a = passo(d, 0.95f, 0, t);
      if (a == Acao::ALERTA_NOVO) { ++novos; t_novo = t; }
      if (a == Acao::ATUALIZACAO) { ++atual; VERIFICA(t - t_novo >= 300, "atualização cedo demais"); t_novo = t; }
    }
    VERIFICA(novos == 1, "exatamente 1 alerta novo"); VERIFICA(atual == 2, "2 atualizações em 12 min");
  }
  { // 5. 60 s de silêncio encerra o evento; novo som abre novo evento
    Decisor d; for (uint32_t t = 0; t < 30; t += 3) passo(d, 0.95f, 0, t);
    VERIFICA(d.em_evento(), "deveria estar em evento");
    Acao fim = Acao::NENHUMA; uint32_t t = 30;
    for (; t < 200 && fim != Acao::FIM_DE_EVENTO; t += 3) fim = passo(d, 0.05f, 0, t);
    VERIFICA(fim == Acao::FIM_DE_EVENTO && !d.em_evento(), "fim de evento");
    Acao a = Acao::NENHUMA; for (int i = 0; i < 4; ++i) { Acao x = passo(d, 0.95f, 0, t + 3 * i); if (x == Acao::ALERTA_NOVO) a = x; }
    VERIFICA(a == Acao::ALERTA_NOVO, "novo evento após o fim do anterior");
  }
  { // 6. motor não gera alerta na fase 1, mas gera quando habilitado
    Decisor d; for (uint32_t t = 0; t < 60; t += 3) VERIFICA(passo(d, 0.05f, 0.99f, t) == Acao::NENHUMA, "motor desabilitado");
    ParametrosDecisao p; p.motor_gera_alerta = true; Decisor e(p); Acao a = Acao::NENHUMA; uint8_t c = 0;
    for (uint32_t t = 0; t < 12; t += 3) { Acao x = passo(e, 0.05f, 0.99f, t, &c); if (x == Acao::ALERTA_NOVO) a = x; }
    VERIFICA(a == Acao::ALERTA_NOVO && c == CL_MOTOR, "motor habilitado");
  }
  { // 7. pico alternado (trovão, galho) não alerta
    Decisor d; for (uint32_t t = 0; t < 600; t += 3) VERIFICA(passo(d, (t / 3) % 2 ? 0.99f : 0.1f, 0, t) == Acao::NENHUMA, "alternado");
  }
  { // 8. limiar exato conta como positivo; logo abaixo não
    Decisor d; Acao a = Acao::NENHUMA;
    for (uint32_t t = 0; t < 9; t += 3) a = passo(d, 0.80f, 0, t);
    VERIFICA(a == Acao::ALERTA_NOVO, "0,80 é positivo");
    Decisor e; a = Acao::NENHUMA; for (uint32_t t = 0; t < 30; t += 3) a = passo(e, 0.7999f, 0, t);
    VERIFICA(a == Acao::NENHUMA, "0,7999 não é");
  }
  { // 9. relógio que dá a volta (uint32) não pode gerar atualização espúria no início do evento
    Decisor d; uint32_t t0 = 0xFFFFFFF0u; int atual = 0;
    for (int i = 0; i < 6; ++i) if (passo(d, 0.95f, 0, t0 + 3 * i) == Acao::ATUALIZACAO) ++atual;
    VERIFICA(atual == 0, "sem atualização espúria na volta do relógio");
  }
}

int main(int argc, char** argv) {
  if (argc < 2) return 2;
  if (!strcmp(argv[1], "decisor")) { cenarios(); printf(falhas ? "REPROVADO (%d falhas)\n" : "decisor: todos os cenários passaram\n", falhas); return falhas ? 1 : 0; }
  if (!strcmp(argv[1], "empacotar")) {
    Alerta a; unsigned s, c, sin, conf, bat, id;
    while (scanf("%u %lf %lf %u %u %u %u %u", &s, &a.latitude, &a.longitude, &c, &sin, &conf, &bat, &id) == 8) {
      a.sensor = s; a.classe = c; a.sinais = sin; a.confianca = conf; a.bateria = bat; a.idade_s = id;
      uint8_t b[TAM_ALERTA]; empacotar(a, b);
      for (int i = 0; i < TAM_ALERTA; ++i) { printf("%02x", b[i]); }
      printf("\n");
    }
    return 0;
  }
  if (!strcmp(argv[1], "desempacotar")) {
    char h[64];
    while (scanf("%63s", h) == 1) {
      uint8_t b[TAM_ALERTA]; for (int i = 0; i < TAM_ALERTA; ++i) { unsigned v; sscanf(h + 2 * i, "%2x", &v); b[i] = v; }
      Alerta a = desempacotar(b);
      printf("%u %.9f %.9f %u %u %u %u %u\n", a.sensor, a.latitude, a.longitude, a.classe, a.sinais, a.confianca, a.bateria, a.idade_s);
    }
    return 0;
  }
  return 2;
}
