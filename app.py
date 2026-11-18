"""Link fixo do painel: guarda o endereço atual do túnel (que muda quando o PC reinicia) e redireciona.
O PC manda o link novo em POST /atualizar com o cabeçalho X-Token (= variável TOKEN do Render).
Só aceita links https://*.trycloudflare.com. Sem dependências (biblioteca padrão)."""
import hmac
import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get("TOKEN", "")
ESTADO = {"link": "", "quando": 0.0}
PADRAO = re.compile(r"^https://[a-z0-9-]+\.trycloudflare\.com/?$")

ESPERA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="10">
<title>Painel</title><style>body{{background:#0b0d12;color:#f2f4f8;font-family:system-ui,sans-serif;
display:grid;place-items:center;min-height:100vh;margin:0;padding:16px;text-align:center}}
.c{{max-width:420px}}h1{{font-size:22px}}p{{color:#9aa3b2}}</style></head><body><div class="c">
<h1>⏳ Esperando o PC</h1><p>{msg}</p><p>Esta página tenta de novo sozinha a cada 10 s.</p></div></body></html>"""


class H(BaseHTTPRequestHandler):
    def _env(self, cod, corpo, tipo="text/html; charset=utf-8", extra=None):
        dados = corpo.encode("utf-8")
        self.send_response(cod)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path.startswith("/status"):
            idade = int(time.time() - ESTADO["quando"]) if ESTADO["quando"] else None
            return self._env(200, json.dumps({"tem_link": bool(ESTADO["link"]), "segundos_desde_aviso": idade}),
                             "application/json")
        recente = ESTADO["link"] and time.time() - ESTADO["quando"] < 15 * 60
        if recente:
            return self._env(302, "", extra={"Location": ESTADO["link"]})
        msg = ("O PC não avisa faz mais de 15 min (desligado ou sem internet)." if ESTADO["link"]
               else "O PC ainda não mandou o link (ele avisa a cada 2 min).")
        return self._env(200, ESPERA.format(msg=msg))

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        if not self.path.startswith("/atualizar"):
            return self._env(404, "não existe")
        tok = self.headers.get("X-Token", "")
        if not TOKEN or not hmac.compare_digest(tok, TOKEN):
            return self._env(403, "token errado")
        n = min(int(self.headers.get("Content-Length") or 0), 300)
        link = self.rfile.read(n).decode("utf-8", "ignore").strip()
        if not PADRAO.match(link):
            return self._env(400, "link inválido")
        ESTADO.update(link=link.rstrip("/"), quando=time.time())
        return self._env(200, "ok")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "10000"))), H).serve_forever()
