"""Gera as imagens de montagem da caixa (montada, explodida, aberta e por trás) a partir das mesmas malhas do gerador.

Requisitos: playwright com chromium e npm (instala three@0.160.0 numa pasta temporária).
Uso: python3 render_montagem.py   ->  imagens/*.png
O painel solar é só um volume de referência (160 x 138 x 3 mm); o desenho dele não é de peça impressa.
"""
import functools, http.server, math, os, shutil, subprocess, tempfile, threading
from pathlib import Path
import trimesh
import gerar_caixa as G
import parametros as P

AQUI = Path(__file__).resolve().parent
SAIDA = AQUI / "imagens"

def painel_no_mundo():
    p = G.cubo(-G.PW / 2, G.PW / 2, -G.PD / 2, G.PD / 2, 0.0, G.PT)
    _, T = G.transformar_berco(G.berco_local())
    return G.para_trimesh(p.rotate((-P.INCLINACAO, 0, 0)).translate(T))

def preparar(tmp):
    (tmp / "stl").mkdir()
    partes, malhas = G.principal()
    malhas = {k: v for k, v in malhas.items() if k != "berco_painel_local"}
    malhas["painel"] = painel_no_mundo()
    for k, m in malhas.items():
        m.export(tmp / "stl" / f"{k}.stl")
    shutil.copy(AQUI / "render_montagem.html", tmp / "index.html")
    if not (AQUI / "node_modules" / "three").exists():
        subprocess.run(["npm", "install", "three@0.160.0"], cwd=tmp, check=True, capture_output=True)
    else:
        os.symlink(AQUI / "node_modules", tmp / "node_modules")
    return malhas

def configurar(malhas, explodido, sem=()):
    # deslocamento vertical (mm) de cada peça na vista explodida
    dz = {"anel_mic": -32, "corpo": 0, "plataforma": 48, "tampa": 78, "perna": 112, "berco_painel": 150, "painel": 188} if explodido else {}
    tipo = {"anel_mic": "anel", "berco_painel": "berco"}
    lista = []
    for k in malhas:
        if k in sem: continue
        t = "perna" if k.startswith("perna_") else tipo.get(k, k)
        lista.append({"arq": k, "tipo": t, "dz": dz.get("perna" if t == "perna" else k, 0)})
    return lista

def principal():
    from playwright.sync_api import sync_playwright
    SAIDA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    malhas = preparar(tmp)
    class Quieto(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k): pass
    h = functools.partial(Quieto, directory=str(tmp))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/index.html"
    pernas = [(x, y) for (x, y) in P.PERNA_POS]
    vistas = [
        ("01_montada_frente", dict(w=1500, h=1100, dir=(0.9, 1.3, 0.5), titulo="EcoVoz, sensor montado", sub="vista frontal (lado do painel mais baixo) · medidas no desenho técnico", partes=configurar(malhas, False))),
        ("02_montada_tras", dict(w=1500, h=1100, dir=(-0.9, -1.3, 0.5), titulo="EcoVoz, sensor montado", sub="vista traseira (face de contato com o tronco, túneis da cinta)", partes=configurar(malhas, False))),
        ("03_explodida", dict(w=1300, h=1700, dir=(0.9, 1.3, 0.55), titulo="Ordem de montagem (vista explodida)", sub="de baixo para cima: 3, 1, 2, 4, 5, 6, 7", partes=configurar(malhas, True),
                              linhas=[[[x, y, -5], [x, y, 210]] for (x, y) in pernas])),
        ("04_aberta", dict(w=1500, h=1100, dir=(0.6, 1.2, 1.35), titulo="Caixa aberta, sem tampa e sem berço", sub="a plataforma (2) fica a 38 mm do piso; bateria e placa não estão modelados", partes=configurar(malhas, False, sem=("tampa", "berco_painel", "painel", "perna_0", "perna_1", "perna_2", "perna_3")))),
        ("05_por_baixo", dict(w=1500, h=1100, dir=(0.5, 0.9, -0.8), titulo="Vista por baixo", sub="furo do microfone com anel pinga-água (3) no piso", partes=configurar(malhas, False))),
    ]
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for nome, cfg in vistas:
            pg = nav.new_page(viewport={"width": cfg["w"], "height": cfg["h"]})
            pg.on("console", lambda m: print("  [navegador]", m.text) if m.type == "error" else None)
            pg.goto(url); pg.wait_for_function("window.pronto === true", timeout=30000)
            pg.evaluate("cfg => window.montar(cfg)", cfg)
            pg.screenshot(path=str(SAIDA / f"{nome}.png"))
            print("gravado", SAIDA / f"{nome}.png")
            pg.close()
        nav.close()
    srv.shutdown(); shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    principal()
