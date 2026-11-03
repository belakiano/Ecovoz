// Sensor acústico EcoVoz: escuta 1 s a cada 3 s, classifica no próprio chip e envia alertas de 12 bytes por LoRaWAN.
// ATENÇÃO: este arquivo NÃO foi compilado nem testado em hardware. A lógica portátil que ele usa
// (nucleo/atributos.hpp e nucleo/alerta.hpp) foi testada no computador; o restante precisa de validação na bancada.
#include <Arduino.h>
#include <Preferences.h>
#include <RadioLib.h>
#include <driver/i2s_std.h>
#include <esp_sleep.h>
#include <TensorFlowLite_ESP32.h>
#include <tensorflow/lite/micro/micro_interpreter.h>
#include <tensorflow/lite/micro/micro_mutable_op_resolver.h>
#include <tensorflow/lite/schema/schema_generated.h>

#include "pinos.h"
#include "segredos.h"          // copie de segredos.exemplo.h
#include "modelo_dados.h"      // gerado por treino/exportar.py
#include "atributos.hpp"
#include "alerta.hpp"

using namespace ecovoz;

// ---------------- configuração ----------------
static const uint32_t CICLO_MS = 3000;            // período entre janelas
static const uint32_t AQUECIMENTO_MIC_MS = 100;   // o INMP441 precisa de ~85 ms para estabilizar
static const uint32_t BATIMENTO_S = 6UL * 3600UL; // mensagem de saúde a cada 6 h
static const uint8_t  PORTA_ALERTA = 1;
static const int      TAM_ARENA = 48 * 1024;      // ajuste após medir interpreter.arena_used_bytes()

// ---------------- estado ----------------
static Preferences prefs;
static uint16_t id_sensor = 0;
static double lat = 0.0, lon = 0.0;
static bool posicao_gnss = false;
static bool reiniciou = true;

static i2s_chan_handle_t canal_rx = nullptr;
static int16_t pcm[JANELA];
static float atributos_f[N_QUADROS * N_MELS];
static ExtratorAtributos extrator;
static Decisor decisor;

alignas(16) static uint8_t arena[TAM_ARENA];
static tflite::MicroInterpreter* interprete = nullptr;
static TfLiteTensor *entrada = nullptr, *saida = nullptr;

SX1262 radio = new Module(PINO_LORA_NSS, PINO_LORA_DIO1, PINO_LORA_RST, PINO_LORA_BUSY);
LoRaWANNode noh(&radio, &AU915, 2);   // sub-banda 2 (canais 8 a 15), a usada pela The Things Network no Brasil

// ---------------- utilidades ----------------
static uint8_t percentual_bateria() {
  // divisor 1:1, referência 3,3 V; curva LiFePO4 aproximada. CALIBRAR com a bateria real.
  const int mv = analogReadMilliVolts(PINO_BATERIA) * 2;
  static const int tab_mv[] = {2900, 3000, 3200, 3250, 3300, 3330, 3400, 3500};
  static const int tab_pc[] = {0, 5, 15, 30, 55, 80, 95, 100};
  if (mv <= tab_mv[0]) return 0;
  for (int i = 1; i < 8; ++i)
    if (mv <= tab_mv[i]) return tab_pc[i - 1] + (tab_pc[i] - tab_pc[i - 1]) * (mv - tab_mv[i - 1]) / (tab_mv[i] - tab_mv[i - 1]);
  return 100;
}

static void carregar_config() {
  prefs.begin("ecovoz", false);
  id_sensor = prefs.getUShort("id", 0);
  lat = prefs.getDouble("lat", 0.0);
  lon = prefs.getDouble("lon", 0.0);
  posicao_gnss = prefs.getBool("gnss", false);
}

// Comandos pela serial na instalação: "ID 402", "POS -5.7333 -52.6500"
static void atender_serial() {
  if (!Serial.available()) return;
  String l = Serial.readStringUntil('\n'); l.trim();
  if (l.startsWith("ID ")) { id_sensor = l.substring(3).toInt(); prefs.putUShort("id", id_sensor); Serial.printf("id=%u\n", id_sensor); }
  else if (l.startsWith("POS ")) {
    double a, b; if (sscanf(l.c_str() + 4, "%lf %lf", &a, &b) == 2) { lat = a; lon = b; prefs.putDouble("lat", a); prefs.putDouble("lon", b); Serial.printf("pos=%.6f %.6f\n", a, b); }
  }
}

// ---------------- microfone ----------------
static void iniciar_i2s() {
  i2s_chan_config_t cc = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  ESP_ERROR_CHECK(i2s_new_channel(&cc, nullptr, &canal_rx));
  i2s_std_config_t sc = {
    .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(TAXA_HZ),
    .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
    .gpio_cfg = {.mclk = I2S_GPIO_UNUSED, .bclk = (gpio_num_t)PINO_I2S_SCK, .ws = (gpio_num_t)PINO_I2S_WS,
                 .dout = I2S_GPIO_UNUSED, .din = (gpio_num_t)PINO_I2S_SD, .invert_flags = {false, false, false}},
  };
  sc.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
  ESP_ERROR_CHECK(i2s_channel_init_std_mode(canal_rx, &sc));
}

// Captura 1 s (JANELA amostras) em pcm[]. Descarta o início enquanto o microfone estabiliza.
static bool capturar_janela() {
  static int32_t bruto[512];
  size_t lidos;
  if (i2s_channel_enable(canal_rx) != ESP_OK) return false;
  const uint32_t descartar = (TAXA_HZ * AQUECIMENTO_MIC_MS) / 1000;
  uint32_t n = 0, pulados = 0;
  const uint32_t limite = millis() + 2500;
  while (n < (uint32_t)JANELA && millis() < limite) {
    if (i2s_channel_read(canal_rx, bruto, sizeof(bruto), &lidos, 200) != ESP_OK) continue;
    for (size_t i = 0; i < lidos / 4 && n < (uint32_t)JANELA; ++i) {
      if (pulados < descartar) { ++pulados; continue; }
      pcm[n++] = (int16_t)(bruto[i] >> 16);   // 24 bits alinhados à esquerda em 32: os 16 mais significativos
    }
  }
  i2s_channel_disable(canal_rx);
  return n == (uint32_t)JANELA;
}

// ---------------- modelo ----------------
static bool iniciar_modelo() {
  static tflite::MicroMutableOpResolver<OPS_DO_MODELO_N> resolver;
  OPS_DO_MODELO_ADICIONAR(resolver);                 // gerado por exportar.py
  const tflite::Model* m = tflite::GetModel(modelo_tflite);
  if (m->version() != TFLITE_SCHEMA_VERSION) return false;
  static tflite::MicroInterpreter i(m, resolver, arena, TAM_ARENA);
  interprete = &i;
  if (interprete->AllocateTensors() != kTfLiteOk) return false;
  entrada = interprete->input(0); saida = interprete->output(0);
  Serial.printf("arena usada: %u de %d bytes\n", (unsigned)interprete->arena_used_bytes(), TAM_ARENA);
  return true;
}

// Retorna as probabilidades (ambiente, motosserra, motor)
static void classificar(float p[3]) {
  extrator.extrair(pcm, atributos_f);
  ExtratorAtributos::quantizar(atributos_f, entrada->data.int8, N_QUADROS * N_MELS, MODELO_ENTRADA_ESCALA, MODELO_ENTRADA_ZP);
  interprete->Invoke();
  for (int k = 0; k < 3; ++k) p[k] = (saida->data.int8[k] - MODELO_SAIDA_ZP) * MODELO_SAIDA_ESCALA;
}

// ---------------- rádio ----------------
static bool iniciar_lora() {
  int16_t e = radio.begin();
  radio.setRfSwitchPins(PINO_LORA_RXEN, PINO_LORA_TXEN);
  if (e != RADIOLIB_ERR_NONE) return false;
  e = noh.beginOTAA(JOIN_EUI, DEV_EUI, NWK_KEY, APP_KEY);
  if (e != RADIOLIB_ERR_NONE) return false;
  for (int t = 0; t < 5; ++t) { if (noh.activateOTAA() == RADIOLIB_LORAWAN_NEW_SESSION) return true; delay(10000); }
  return false;
}

static void enviar(uint8_t classe, uint8_t sinais, float confianca, uint8_t idade_s) {
  Alerta a;
  a.sensor = id_sensor; a.latitude = lat; a.longitude = lon; a.classe = classe;
  a.sinais = sinais | (posicao_gnss ? SIN_POSICAO_GNSS : 0) | (reiniciou ? SIN_REINICIO : 0);
  a.bateria = percentual_bateria(); if (a.bateria < 20) a.sinais |= SIN_BATERIA_BAIXA;
  a.confianca = (uint8_t)lroundf(constrain(confianca, 0.0f, 1.0f) * 255.0f);
  a.idade_s = idade_s;
  uint8_t carga[TAM_ALERTA]; empacotar(a, carga);
  const int16_t e = noh.sendReceive(carga, TAM_ALERTA, PORTA_ALERTA);
  Serial.printf("envio classe=%u conf=%u bat=%u resultado=%d\n", classe, a.confianca, a.bateria, e);
  if (e >= 0) reiniciou = false;
}

// ---------------- ciclo principal ----------------
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  carregar_config();
  iniciar_i2s();
  if (!iniciar_modelo()) { Serial.println("falha ao iniciar o modelo"); while (true) delay(1000); }
  if (!iniciar_lora())   { Serial.println("falha ao entrar na rede LoRaWAN, seguirá tentando no batimento"); }
  enviar(CL_BATIMENTO, 0, 0.0f, 0);
}

void loop() {
  const uint32_t t_ini = millis();
  const uint32_t t_s = t_ini / 1000;
  atender_serial();

  if (capturar_janela()) {
    float p[3]; classificar(p);
    uint8_t classe; float conf;
    const Acao acao = decisor.atualizar(p[1], p[2], t_s, &classe, &conf);
    if (acao == Acao::ALERTA_NOVO) enviar(classe, 0, conf, 0);
    else if (acao == Acao::ATUALIZACAO) enviar(classe, SIN_ATUALIZACAO, conf, (uint8_t)min<uint32_t>(255, decisor.idade_evento_s(t_s)));
  }

  static uint32_t ultimo_batimento_s = 0;
  if (t_s - ultimo_batimento_s >= BATIMENTO_S) { ultimo_batimento_s = t_s; enviar(CL_BATIMENTO, 0, 0.0f, 0); }

  // sono leve até completar o ciclo (mantém a RAM e o estado do decisor)
  const uint32_t gasto = millis() - t_ini;
  if (gasto < CICLO_MS) { esp_sleep_enable_timer_wakeup((uint64_t)(CICLO_MS - gasto) * 1000ULL); esp_light_sleep_start(); }
}
