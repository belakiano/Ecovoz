# 🌲 EcoVoz: Sistema Acústico de Detecção Precoce de Desmatamento com IA na Borda (Edge AI)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Target Platform](https://img.shields.io/badge/Platform-ESP32--S3-blue.svg)](https://www.espressif.com/en/products/socs/esp32-s3)
[![Model Size](https://img.shields.io/badge/TinyML-31KB--int8-green.svg)](https://www.tensorflow.org/lite/micro)
[![Radio Protocol](https://img.shields.io/badge/LoRaWAN-AU915--Subband2-orange.svg)](https://www.thethingsnetwork.org/)

O **EcoVoz** é uma solução de monitoramento bioacústico de baixo custo projetada para detecção precoce de ameaças ambientais (como motosserras e motores de supressão vegetal) em áreas de alta pressão de desmatamento na Amazônia.

Utilizando **Inteligência Artificial na Borda (TinyML)**, o sensor processa o áudio localmente em um microcontrolador ESP32-S3, com o objetivo de ignorar o ruído natural da floresta (chuva, vento, fauna) e transmitir apenas um alerta ultra-leve de **12 bytes** via rádio de longo alcance (**LoRaWAN**).

---

## 🚧 Estado do projeto (fase 1, protótipo de bancada)

| Verificado no computador | Ainda não verificado |
| :--- | :--- |
| Paridade dos atributos entre C++ e Python (erro máximo de 3,2e-6 em áudio real) | Compilação e execução do firmware no ESP32-S3 |
| Carga de 12 bytes idêntica em C++ e Python (1003 casos, 0 bytes divergentes) | Arena do TensorFlow Lite Micro e tempo de inferência |
| Regra de decisão (9 cenários) e servidor (15 testes) | Consumo real, alcance do rádio e geração solar sob a copa |
| Malhas da caixa fechadas e sem colisão entre peças | Impressão e montagem das peças |
| Modelo: recall de 73,6% para motosserra e 4,4% de falsos positivos em janelas de ambiente (validação cruzada de 5 dobras no ESC-50, int8, limiar 0,80) | Desempenho em campo com áudio real de floresta |

Os números do modelo vêm de um banco público de sons, não de campo. Cada dobra de teste tem só 8 clipes de motosserra, a receita de treino foi ajustada olhando duas dobras e o modelo confunde motor com motosserra em até 37% das janelas de algumas dobras. O consumo de 11,3 mA e a autonomia são premissas de projeto (`ferramentas/orcamento_energia.py`), não medições. O detalhamento está em `docs/dossie_tecnico.pdf`.

---

## 📁 Estrutura do Repositório

```text
ecovoz/
├── docs/                      # Dossiê técnico e especificações
│   ├── dossie_tecnico.pdf     # Dossiê técnico de desenvolvimento (PDF do documento, 19 páginas)
│   ├── diagrama_operacao.png  # Arquitetura de operação e transmissão
│   ├── diagrama_operacao.mmd  # Fonte do diagrama (Mermaid)
│   └── protocolo_alerta.md    # Especificação do payload binário de 12 bytes
├── firmware/                  # Código C++ para o sensor (PlatformIO, Arduino-ESP32)
│   ├── platformio.ini         # Configuração de dependências e build
│   └── src/
│       ├── main.cpp           # Loop principal, amostragem I2S, modelo, LoRaWAN e sono leve
│       ├── pinos.h            # Mapeamento de pinos do ESP32-S3
│       ├── modelo_dados.h     # Modelo TFLite int8 como vetor C (gerado por treino/exportar.py)
│       └── segredos.exemplo.h # Template para chaves OTAA LoRaWAN
├── nucleo/                    # Bibliotecas portáteis C++ (testadas no computador e usadas no sensor)
│   ├── atributos.hpp          # Extrator de atributos log-mel (FFT de 512 pontos)
│   ├── alerta.hpp             # Regra de decisão com persistência e empacotador de 12 bytes
│   ├── normalizacao.h         # Média e desvio global (gerado por treino/exportar.py)
│   └── tabelas_atributos.h    # Janela de Hann e filtros mel pré-calculados (gerado por treino/gerar_tabelas.py)
├── treino/                    # Pipeline de Machine Learning em Python (TensorFlow/Keras)
│   ├── treinar.py             # Validação cruzada, treino final e quantização int8
│   ├── atributos.py           # Referência em Python da extração log-mel (paridade com o C++)
│   ├── dados_esc50.py         # Carga e organização do ESC-50 em 3 classes
│   ├── gerar_tabelas.py       # Gera nucleo/tabelas_atributos.h
│   ├── exportar.py            # Converte o TFLite int8 em modelo_dados.h e normalizacao.h
│   ├── experimentos.py        # Experimentos de receita de treino
│   ├── diagnostico.py         # Diagnósticos do modelo
│   ├── normalizacao.json      # Média e desvio global do modelo final
│   └── resultados/            # Métricas da validação cruzada e do modelo final, modelo .tflite
├── caixa/                     # Geradores de peças 3D (ASA ou PETG) e documentação de fabricação
│   ├── parametros.py          # Todas as dimensões em mm (única fonte das medidas)
│   ├── gerar_caixa.py         # Gera as malhas (manifold3d e trimesh) e o relatório
│   ├── verificar_caixa.py     # Verifica malhas fechadas, interpenetração e montagem
│   ├── desenho_tecnico.py     # Desenho técnico cotado em SVG
│   ├── render_montagem.py     # Imagens de montagem a partir das malhas
│   ├── render_montagem.html   # Página de renderização usada pelo script acima
│   ├── desenho_tecnico.svg    # Desenho técnico (também em .png)
│   ├── lista_de_materiais.csv # Lista de materiais, colunas de preço em branco
│   ├── imagens/               # Montada, explodida, aberta, traseira e por baixo
│   └── stl/                   # Modelos 3D para impressão
│       ├── corpo.stl          # Caixa principal com cavidade estanque
│       ├── tampa.stl          # Tampa com canaleta para silicone e pinga-água
│       ├── berco_painel.stl   # Suporte inclinado (12°) para painel solar de 3 W
│       ├── plataforma.stl     # Plataforma da placa
│       ├── anel_microfone.stl # Anel pinga-água do microfone
│       ├── perna_dianteira.stl, perna_traseira.stl
│       └── montagem_completa.stl
├── servidor/                  # Backend de recepção e painel (FastAPI + SQLite)
│   ├── servidor.py            # Gancho para ChirpStack / TTN v3, banco e avisos via Telegram
│   ├── decodificador.py       # Decodificador em Python do payload de 12 bytes
│   ├── requirements.txt
│   └── painel/
│       └── index.html         # Painel de fiscalização com mapa
├── testes/                    # Testes e validação cruzada
│   ├── teste_paridade.py      # Paridade de atributos (Python e C++)
│   ├── teste_carga_cruzado.py # Consistência do payload de 12 bytes (C++ e Python)
│   ├── teste_servidor.py      # Testes do servidor FastAPI (pytest)
│   ├── cli_atributos.cpp      # Auxiliar do teste de paridade
│   └── teste_alerta.cpp       # Auxiliar do teste de carga e testes da regra de decisão
├── ferramentas/
│   └── orcamento_energia.py   # Orçamento de energia com as premissas declaradas
├── requirements.txt           # Dependências de treino, testes e caixa
├── LICENSE
└── README.md
```

---

## ⚡ Arquitetura Técnica & Especificações

### 1. Hardware do Sensor (Bancada)
* **Processador & IA:** ESP32-S3 (Dual-Core 240 MHz, 512 KB SRAM).
* **Captação de Áudio:** Microfone MEMS I2S Digital 16 kHz (ex: INMP441).
* **Comunicação Sem Fio:** Transceptor SX1262 LoRa (915 MHz, AU915 Sub-banda 2).
* **Alimentação:** Bateria LiFePO4 26650 (3.2V / 3000 mAh) + Painel Solar 3W (6V) gerenciado por carregador MPPT.
* **Consumo Estimado:** 11.3 mA em média, premissa de projeto (amostragem ativa de 1.15 s a cada 3 s), ainda não medida.

### 2. Modelo TinyML (Classificação Acústica)
* **Arquitetura:** CNN com convoluções separáveis (Depthwise Separable 3x3).
* **Tamanho do Modelo:** 31.9 KB (31.864 bytes, quantizado em `int8`; 12.531 parâmetros).
* **Operações por Inferência:** ~0.453 milhões de MACs.
* **Classes:** `0: Ambiente (Fauna/Chuva/Vento)`, `1: Motosserra`, `2: Motor`. Na fase 1 só a motosserra gera alerta; a classe de fogo está reservada no protocolo e fora desta fase.

### 3. Protocolo de Transmissão (12 Bytes Payload)
Em vez de streaming de áudio (inviável em redes florestais), o sensor envia um pacote binário otimizado contendo:

| Bytes | Campo | Descrição |
| :--- | :--- | :--- |
| `0-1` | Sensor ID | Identificador único do dispositivo (0-65535) |
| `2-4` | Latitude | Posição quantizada em 24 bits (~1.2m de resolução) |
| `5-7` | Longitude | Posição quantizada em 24 bits (~2.4m de resolução no equador) |
| `8` | Classe / Sinais | 4 bits de Classe + 4 bits de Status (Bateria Baixa, GNSS, etc.) |
| `9` | Confiança | Confiança do modelo de IA (0 a 255 representando 0-100%) |
| `10` | Bateria | Percentual de carga residual (0-100%) |
| `11` | Idade do Evento | Tempo em segundos desde o início da detecção |

---

## 🛠️ Como Executar e Validar

### 1. Testes no computador (paridade C++ e Python, carga, decisor)
Requer Python 3.13, um compilador C++17 e `pip install -r requirements.txt`. O teste de paridade usa clipes reais do ESC-50, então rode antes o `git clone` do passo 3.
```bash
cd testes
g++ -O2 -std=c++17 -o cli_atributos cli_atributos.cpp
g++ -O1 -std=c++17 -fsanitize=address,undefined -o teste_alerta teste_alerta.cpp
python3 teste_paridade.py
./teste_alerta decisor
python3 teste_carga_cruzado.py
python3 -m pytest -q teste_servidor.py
```

### 2. Rodar o Servidor Local de Alertas
```bash
cd servidor
pip install -r requirements.txt
export ECOVOZ_TOKEN="seu_token_seguro"
uvicorn servidor:app --reload --port 8000
```
Acesse o painel web em `http://localhost:8000`. O token protege o gancho e a mudança de estado dos alertas; a leitura do painel e da API não pede token, então ponha o servidor atrás de rede privada ou proxy com autenticação.

### 3. Treinar e exportar o modelo (opcional)
```bash
git clone https://github.com/karolpiczak/ESC-50 dados/ESC-50
cd treino
python3 gerar_tabelas.py
python3 treinar.py --cv      # validação cruzada, cerca de 5 min por dobra
python3 treinar.py --final   # modelo final
python3 exportar.py          # atualiza firmware/src/modelo_dados.h e nucleo/normalizacao.h
```

### 4. Gerar a caixa
```bash
cd caixa
python3 gerar_caixa.py && python3 verificar_caixa.py && python3 desenho_tecnico.py
python3 render_montagem.py   # opcional, precisa de playwright e npm
```
Confira as medidas marcadas com `[CONFERIR]` em `caixa/parametros.py` contra as peças compradas antes de imprimir.

### 5. Compilar o Firmware (PlatformIO)
O firmware **ainda não foi compilado nem testado em hardware**, e as versões das bibliotecas em `platformio.ini` precisam ser confirmadas na primeira compilação. Abra a pasta `firmware/` no VS Code com a extensão **PlatformIO**:
1. Copie `firmware/src/segredos.exemplo.h` para `segredos.h` (ignorado pelo Git) e insira as chaves OTAA da sua rede LoRaWAN (TTN/ChirpStack).
2. Confira a pinagem em `pinos.h` e execute:
```bash
pio run -e sensor --target upload
```

---

## ⚖️ Licença e Ética

* **Licença de Código:** MIT License.
* **Conjunto de Dados de Treino:** O modelo padrão foi treinado utilizando recortes do dataset [ESC-50](https://github.com/karolpiczak/ESC-50) (licença CC BY-NC 3.0, apenas para fins de pesquisa). Por precaução, trate os pesos do modelo (`firmware/src/modelo_dados.h` e `treino/resultados/modelo_ecovoz_int8.tflite`) como restritos a uso não comercial até haver treino com dados próprios ou de licença adequada.
* **Privacidade:** O firmware foi projetado para **não gravar nem transmitir áudio**: a inferência ocorre na memória volátil (RAM) e só saem do sensor os 12 bytes do alerta. Isso precisa ser confirmado no firmware em hardware.
* **Segurança dos alertas:** as coordenadas mostram onde há atividade. Um alerta não é prova: confirme com um humano antes de despachar uma equipe. Testes de campo apenas com autorização do responsável pela área.

---

*Desenvolvido no âmbito do projeto EcoVoz (#AIforImpact2026).*