"""Testes do decodificador e do servidor de alertas (pytest)."""
import base64, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "servidor"))

_dir = tempfile.mkdtemp()
os.environ["ECOVOZ_BANCO"] = os.path.join(_dir, "t.db")
os.environ["ECOVOZ_TOKEN"] = "segredo-de-teste"

import pytest
from fastapi.testclient import TestClient
import decodificador as D
import servidor

cliente = TestClient(servidor.app)
H = {"X-EcoVoz-Token": "segredo-de-teste"}

def carga(**kw):
    base = dict(sensor=402, latitude=-5.7333, longitude=-52.6500, classe=1, sinais=1, confianca=0.984, bateria=88, idade_s=12)
    base.update(kw); return D.codificar(**base)

def ttn(dados, dev="eco-402", cnt=10, hora="2026-11-01T15:00:12Z"):
    return {"end_device_ids": {"device_id": dev, "dev_eui": "70B3D57ED0000402"},
            "received_at": hora,
            "uplink_message": {"f_port": 1, "f_cnt": cnt, "frm_payload": base64.b64encode(dados).decode(),
                               "rx_metadata": [{"gateway_ids": {"gateway_id": "gw-a"}, "time": hora, "rssi": -112, "snr": 3.5},
                                               {"gateway_ids": {"gateway_id": "gw-b"}, "time": hora, "rssi": -98, "snr": 7.0}]}}

def test_ida_e_volta_da_carga():
    a = D.decodificar(carga())
    assert a.sensor == 402 and a.classe == 1 and a.classe_nome == "motosserra"
    assert abs(a.latitude - (-5.7333)) < 2e-5 and abs(a.longitude - (-52.65)) < 3e-5   # resolução do formato
    assert abs(a.confianca - 0.984) < 0.003 and a.bateria == 88 and a.idade_s == 12

def test_resolucao_espacial_em_metros():
    # 1 passo de latitude = 180/2^24 graus = ~1,19 m ; 1 passo de longitude no equador = 360/2^24 graus = ~2,39 m
    assert abs(180 / 2**24 * 111_320 - 1.19) < 0.02 and abs(360 / 2**24 * 111_320 - 2.39) < 0.02

@pytest.mark.parametrize("n", [0, 11, 13, 50])
def test_tamanho_invalido(n):
    with pytest.raises(ValueError): D.decodificar(bytes(n))

def test_extremos_de_coordenadas():
    for lat, lon in [(-90, -180), (90, 180), (0, 0)]:
        a = D.decodificar(D.codificar(1, lat, lon, 1))
        assert -90 <= a.latitude <= 90 and -180 <= a.longitude <= 180

def test_gancho_sem_token_e_com_token_errado():
    assert cliente.post("/gancho/lorawan", json=ttn(carga())).status_code == 401
    assert cliente.post("/gancho/lorawan", json=ttn(carga()), headers={"X-EcoVoz-Token": "errado"}).status_code == 401

def test_gancho_ttn_grava_e_escolhe_melhor_gateway():
    r = cliente.post("/gancho/lorawan", json=ttn(carga()), headers=H)
    assert r.status_code == 200 and r.json()["novo"] is True and r.json()["classe"] == "motosserra"
    a = cliente.get("/api/alertas").json()[0]
    assert a["rssi"] == -98 and a["gateway"] == "gw-b" and a["sensor"] == 402
    # horário do evento = recebimento menos a idade informada pelo sensor
    assert a["evento_em"].startswith("2026-11-01T15:00:00")

def test_repeticao_do_mesmo_quadro_nao_duplica():
    corpo = ttn(carga(sensor=500), dev="eco-500", cnt=77)
    assert cliente.post("/gancho/lorawan", json=corpo, headers=H).json()["novo"] is True
    assert cliente.post("/gancho/lorawan", json=corpo, headers=H).json()["novo"] is False
    assert sum(1 for a in cliente.get("/api/alertas?limite=1000").json() if a["sensor"] == 500) == 1

def test_chirpstack_v4():
    corpo = {"deviceInfo": {"devEui": "70b3d57ed0000403", "deviceName": "eco-403"}, "fPort": 1, "fCnt": 5,
             "data": base64.b64encode(carga(sensor=403, classe=2)).decode(),
             "rxInfo": [{"gatewayId": "gw-c", "rssi": -105, "snr": 4.0, "nsTime": "2026-11-01T16:00:00+00:00"}]}
    assert cliente.post("/gancho/lorawan", json=corpo, headers=H).json()["classe"] == "motor"

def test_batimento_nao_aparece_na_lista_de_alertas_mas_atualiza_sensor():
    b = D.codificar(sensor=600, latitude=-5.0, longitude=-52.0, classe=0, bateria=71)
    assert cliente.post("/gancho/lorawan", json=ttn(b, dev="eco-600", cnt=1), headers=H).status_code == 200
    assert all(a["sensor"] != 600 for a in cliente.get("/api/alertas?limite=1000").json())
    s = {x["sensor"]: x for x in cliente.get("/api/sensores").json()}
    assert s[600]["bateria"] == 71

def test_formato_desconhecido_e_carga_invalida_retornam_422():
    assert cliente.post("/gancho/lorawan", json={"x": 1}, headers=H).status_code == 422
    assert cliente.post("/gancho/lorawan", json=ttn(b"\x00" * 5), headers=H).status_code == 422

def test_mudar_status_exige_token_e_valida():
    a = cliente.get("/api/alertas").json()[0]
    assert cliente.post(f"/api/alertas/{a['id']}/status", json={"status": "confirmado"}).status_code == 401
    assert cliente.post(f"/api/alertas/{a['id']}/status", json={"status": "inventado"}, headers=H).status_code == 422
    assert cliente.post(f"/api/alertas/{a['id']}/status", json={"status": "confirmado"}, headers=H).status_code == 200
    assert cliente.get("/api/alertas?status=confirmado").json()[0]["id"] == a["id"]

def test_painel_e_saude():
    assert cliente.get("/saude").json() == {"ok": True}
    assert "EcoVoz" in cliente.get("/").text
