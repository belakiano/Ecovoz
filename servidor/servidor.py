"""Servidor de alertas do EcoVoz.

Recebe os avisos da rede LoRaWAN por gancho web (TTN v3 ou ChirpStack v4), decodifica a carga de 12 bytes,
guarda em SQLite, avisa por Telegram (opcional) e serve o painel com mapa.

Variáveis de ambiente:
  ECOVOZ_TOKEN        segredo do gancho web (cabeçalho X-EcoVoz-Token). Obrigatório em produção.
  ECOVOZ_BANCO        caminho do SQLite (padrão: ecovoz.db)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   opcionais, ativam o aviso por Telegram
  ECOVOZ_CONFIANCA_MIN  confiança mínima, de 0 a 1, para avisar (padrão 0.0)

Execução:  uvicorn servidor:app --host 0.0.0.0 --port 8000
"""
import base64
import hmac
import os
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from decodificador import decodificar

PASTA = Path(__file__).resolve().parent
_trava = threading.Lock()


def banco():
    caminho = os.environ.get("ECOVOZ_BANCO", str(PASTA / "ecovoz.db"))
    con = sqlite3.connect(caminho, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS alertas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, recebido_em TEXT NOT NULL, evento_em TEXT,
        dispositivo TEXT, sensor INTEGER, latitude REAL, longitude REAL, classe INTEGER, classe_nome TEXT,
        confianca REAL, bateria INTEGER, idade_s INTEGER, sinais INTEGER, atualizacao INTEGER,
        contador_enlace INTEGER, rssi REAL, snr REAL, gateway TEXT, status TEXT NOT NULL DEFAULT 'novo',
        UNIQUE (dispositivo, contador_enlace, recebido_em))""")
    con.execute("""CREATE TABLE IF NOT EXISTS sensores (
        sensor INTEGER PRIMARY KEY, dispositivo TEXT, ultima_msg TEXT, bateria INTEGER, latitude REAL, longitude REAL)""")
    return con


_con = None
def con():
    global _con
    if _con is None:
        _con = banco()
    return _con


def normalizar(corpo: dict):
    """Aceita TTN v3 e ChirpStack v4. Retorna dict com dados (bytes), dispositivo, contador, hora, rssi, snr, gateway."""
    if "uplink_message" in corpo:                                  # The Things Network v3
        u = corpo["uplink_message"]
        rx = (u.get("rx_metadata") or [{}])
        melhor = max(rx, key=lambda r: r.get("rssi", -999)) if rx else {}
        gw = (melhor.get("gateway_ids") or {}).get("gateway_id")
        return {"dados": base64.b64decode(u["frm_payload"]),
                "dispositivo": corpo["end_device_ids"].get("device_id") or corpo["end_device_ids"].get("dev_eui"),
                "contador": u.get("f_cnt"), "hora": melhor.get("time") or corpo.get("received_at"),
                "rssi": melhor.get("rssi"), "snr": melhor.get("snr"), "gateway": gw, "porta": u.get("f_port")}
    if "deviceInfo" in corpo and "data" in corpo:                  # ChirpStack v4
        rx = corpo.get("rxInfo") or [{}]
        melhor = max(rx, key=lambda r: r.get("rssi", -999))
        return {"dados": base64.b64decode(corpo["data"]),
                "dispositivo": corpo["deviceInfo"].get("deviceName") or corpo["deviceInfo"].get("devEui"),
                "contador": corpo.get("fCnt"), "hora": melhor.get("nsTime") or corpo.get("time"),
                "rssi": melhor.get("rssi"), "snr": melhor.get("snr"), "gateway": melhor.get("gatewayId"), "porta": corpo.get("fPort")}
    raise ValueError("formato de gancho web não reconhecido")


def hora_utc(texto):
    if not texto:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(timezone.utc)


def avisar_telegram(a):
    tk, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tk and chat):
        return
    texto = (f"ALERTA EcoVoz: {a['classe_nome']}\nSensor {a['sensor']} ({a['dispositivo']})\n"
             f"Posição {a['latitude']:.5f}, {a['longitude']:.5f}\nConfiança {a['confianca']*100:.0f}%  "
             f"Bateria {a['bateria']}%\nhttps://www.google.com/maps?q={a['latitude']:.5f},{a['longitude']:.5f}")
    dados = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tk}/sendMessage", data=dados), timeout=10)
    except Exception as e:                                          # o aviso não pode derrubar o recebimento
        print("falha no Telegram:", e)


app = FastAPI(title="EcoVoz", version="0.1")


@app.post("/gancho/lorawan")
async def gancho(req: Request, x_ecovoz_token: str = Header(default="")):
    esperado = os.environ.get("ECOVOZ_TOKEN", "")
    if not esperado or not hmac.compare_digest(x_ecovoz_token, esperado):
        raise HTTPException(status_code=401, detail="token inválido")
    try:
        n = normalizar(await req.json())
        a = decodificar(n["dados"]).para_dict()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    recebido = hora_utc(n["hora"])
    evento = datetime.fromtimestamp(recebido.timestamp() - a["idade_s"], timezone.utc)
    with _trava:
        c = con()
        c.execute("""INSERT OR IGNORE INTO alertas (recebido_em, evento_em, dispositivo, sensor, latitude, longitude, classe,
            classe_nome, confianca, bateria, idade_s, sinais, atualizacao, contador_enlace, rssi, snr, gateway)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (recebido.isoformat(), evento.isoformat(), n["dispositivo"], a["sensor"], a["latitude"], a["longitude"],
                   a["classe"], a["classe_nome"], a["confianca"], a["bateria"], a["idade_s"], a["sinais"], int(a["atualizacao"]),
                   n["contador"], n["rssi"], n["snr"], n["gateway"]))
        novo = c.execute("SELECT changes()").fetchone()[0] == 1
        c.execute("""INSERT INTO sensores (sensor, dispositivo, ultima_msg, bateria, latitude, longitude) VALUES (?,?,?,?,?,?)
            ON CONFLICT(sensor) DO UPDATE SET dispositivo=excluded.dispositivo, ultima_msg=excluded.ultima_msg,
            bateria=excluded.bateria, latitude=excluded.latitude, longitude=excluded.longitude""",
                  (a["sensor"], n["dispositivo"], recebido.isoformat(), a["bateria"], a["latitude"], a["longitude"]))
        c.commit()
    # só avisa por Telegram detecções reais (não batimento), novas (não repetição do mesmo quadro) e acima da confiança mínima
    minimo = float(os.environ.get("ECOVOZ_CONFIANCA_MIN", "0"))
    if novo and a["classe"] != 0 and a["confianca"] >= minimo and not a["atualizacao"]:
        threading.Thread(target=avisar_telegram, args=({**a, "dispositivo": n["dispositivo"]},), daemon=True).start()
    return {"ok": True, "novo": novo, "classe": a["classe_nome"]}


@app.get("/api/alertas")
def listar(limite: int = 100, status: str | None = None):
    sql, args = "SELECT * FROM alertas WHERE classe != 0", []
    if status:
        sql += " AND status = ?"; args.append(status)
    sql += " ORDER BY id DESC LIMIT ?"; args.append(min(limite, 1000))
    with _trava:
        return [dict(r) for r in con().execute(sql, args)]


@app.get("/api/sensores")
def sensores():
    with _trava:
        linhas = [dict(r) for r in con().execute("SELECT * FROM sensores ORDER BY sensor")]
    agora = time.time()
    for s in linhas:
        s["silencio_h"] = round((agora - hora_utc(s["ultima_msg"]).timestamp()) / 3600, 2)
        s["sem_sinal"] = s["silencio_h"] > 13     # batimento esperado a cada 6 h; 2 perdas seguidas = alerta de saúde
    return linhas


@app.post("/api/alertas/{id}/status")
def mudar_status(id: int, req_status: dict, x_ecovoz_token: str = Header(default="")):
    esperado = os.environ.get("ECOVOZ_TOKEN", "")
    if not esperado or not hmac.compare_digest(x_ecovoz_token, esperado):
        raise HTTPException(status_code=401, detail="token inválido")
    novo = req_status.get("status")
    if novo not in ("novo", "em_verificacao", "confirmado", "falso_alarme"):
        raise HTTPException(status_code=422, detail="status inválido")
    with _trava:
        c = con(); c.execute("UPDATE alertas SET status=? WHERE id=?", (novo, id)); c.commit()
    return {"ok": True}


@app.get("/saude")
def saude():
    return {"ok": True}


@app.get("/")
def painel():
    return FileResponse(PASTA / "painel" / "index.html")
