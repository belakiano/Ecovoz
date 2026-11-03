// Ligações do protótipo de bancada (ESP32-S3-DevKitC-1). Escolhi pinos livres e sem função de boot.
// Se usar outra placa, altere só este arquivo.
#pragma once
// Microfone MEMS I2S (INMP441): L/R ligado ao GND = canal esquerdo
#define PINO_I2S_SCK   4    // BCLK
#define PINO_I2S_WS    5    // LRCLK
#define PINO_I2S_SD    6    // dados do microfone
// Módulo LoRa SX1262 (E22-900M22S), SPI
#define PINO_LORA_SCK  12
#define PINO_LORA_MISO 13
#define PINO_LORA_MOSI 11
#define PINO_LORA_NSS  10
#define PINO_LORA_RST  9
#define PINO_LORA_BUSY 8
#define PINO_LORA_DIO1 7
#define PINO_LORA_RXEN 15
#define PINO_LORA_TXEN 16
// Medida da bateria: divisor resistivo 1:1 (2 x 100 kohm) no ADC
#define PINO_BATERIA   1
// Alimentação chaveada do microfone (opcional, via MOSFET canal P). -1 = sempre ligado
#define PINO_MIC_ENERGIA -1
