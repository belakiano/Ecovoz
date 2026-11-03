# Protocolo do alerta EcoVoz (12 bytes)

Porta LoRaWAN 1. Ordem dos bytes: grande-endiano. Implementações idênticas em `nucleo/alerta.hpp` (sensor) e
`servidor/decodificador.py` (servidor), conferidas byte a byte por `testes/teste_carga_cruzado.py`.

| Bytes | Campo | Codificação |
|---|---|---|
| 0 a 1 | Sensor | inteiro de 16 bits, 0 a 65535 |
| 2 a 4 | Latitude | `round((lat + 90) / 180 * 2^24)`, passo de 1,19 m |
| 5 a 7 | Longitude | `round((lon + 180) / 360 * 2^24)`, passo de 2,39 m no equador |
| 8 | Classe (4 bits altos) e sinais (4 bits baixos) | classe: 0 batimento, 1 motosserra, 2 motor, 3 fogo (reservado) |
| 9 | Confiança | 0 a 255 representa 0 a 100 % |
| 10 | Bateria | 0 a 100 % |
| 11 | Idade do evento | segundos desde a primeira detecção, saturado em 255 |

Sinais (bits 0 a 3): 1 posição por GNSS, 2 atualização de evento em curso, 4 bateria baixa, 8 reinício do sensor.

O horário do evento não vai na carga: o servidor usa a hora de recepção no gateway menos a idade do evento.
Erro de posição medido em 200 mil pontos dentro do Brasil: no máximo 0,6 m em latitude e 1,0 m em longitude.

Tempo no ar com 25 bytes (12 de carga e 13 de cabeçalho LoRaWAN), 125 kHz: SF7 62 ms, SF9 206 ms, SF10 412 ms.
O ciclo de trabalho de 1 % de cada sub-banda não é problema nesse padrão de uso, mas verifique a regra vigente da Anatel para a faixa.
