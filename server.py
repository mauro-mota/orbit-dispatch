"""Servidor do laboratório local. Comece pelas funções de regras.py."""
import argparse
import json
import logging
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from regras import ErroQuiz, obter_jogo, responder_pergunta

ROOT = Path(__file__).resolve().parent / "static"
MAX_BODY = 4096
LOGGER = logging.getLogger("orbit-dispatch")
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def allowed_host(host):
    """Recusa nomes externos, inclusive os usados em ataques de DNS rebinding."""
    try:
        address = urlsplit("http://" + host)
        return (address.hostname in {"localhost", "127.0.0.1", "::1"}
                and address.port is not None
                and address.username is None and address.password is None
                and not address.path and not address.query and not address.fragment)
    except ValueError:
        return False


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        self.token = secrets.token_urlsafe(24)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def respond(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def respond_json(self, status, data):
        self.respond(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def guarded(self, operation):
        try:
            if not allowed_host(self.headers.get("Host", "")):
                raise ErroQuiz("Abra a central por localhost ou 127.0.0.1, com a porta indicada.", 403)
            operation()
        except ErroQuiz as error:
            self.respond_json(error.status, {"erro": str(error)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            LOGGER.info("A conexão com o navegador foi encerrada.")
        except Exception:
            LOGGER.exception("Falha inesperada na central")
            self.respond_json(500, {"erro": "O servidor encontrou um erro. Confira os registros no terminal."})

    def do_GET(self):
        self.guarded(self.get)

    def do_HEAD(self):
        # Mesmas rotas e cabeçalhos de GET, sem enviar o corpo.
        self.guarded(self.get)

    def get(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/api/saude":
            self.respond_json(200, {"status": "ok"})
        elif parsed.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[parsed.path]
            content = (ROOT / filename).read_bytes()
            if parsed.path == "/":
                content = content.replace(b"__DISPATCH_TOKEN__", self.server.token.encode("ascii"))
            self.respond(200, content, content_type)
        else:
            raise ErroQuiz("Rota não encontrada.", 404)

    def read_json(self):
        if self.headers.get("Transfer-Encoding"):
            raise ErroQuiz("Este exercício não aceita transferência em blocos.", 400)
        if self.headers.get_content_type() != "application/json":
            raise ErroQuiz("Envie Content-Type: application/json.", 415)
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) > 1:
            raise ErroQuiz("Envie um único Content-Length.", 400)
        try:
            size = int(lengths[0] if lengths else "0")
        except ValueError:
            raise ErroQuiz("O tamanho do pedido é inválido.", 400) from None
        if not 0 < size <= MAX_BODY:
            raise ErroQuiz("O JSON precisa ter entre 1 e 4096 bytes.", 413)
        def reject_constant(value):
            raise ValueError("Constante inválida: " + value)
        try:
            payload = json.loads(self.rfile.read(size), parse_constant=reject_constant)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise ErroQuiz("O corpo do pedido não é um JSON válido.", 400) from None
        if not isinstance(payload, dict):
            raise ErroQuiz("Envie um objeto JSON, com campos e valores.")
        return payload

    def do_POST(self):
        self.guarded(self.post)

    def post(self):
        path = urlsplit(self.path).path
        if path not in {"/api/jogo", "/api/responder", "/api/parar"}:
            raise ErroQuiz("Rota não encontrada.", 404)
        token = self.headers.get("X-Dispatch-Token", "").encode("utf-8")
        if not secrets.compare_digest(token, self.server.token.encode("ascii")):
            raise ErroQuiz("Recarregue a página para renovar a proteção de envio.", 403)
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            raise ErroQuiz("A origem deste pedido não é permitida.", 403)
        payload = self.read_json()
        if path == "/api/jogo":
            self.respond_json(200, obter_jogo(payload))
        elif path == "/api/responder":
            self.respond_json(200, responder_pergunta(payload))
        else:
            if payload:
                raise ErroQuiz("Para encerrar a central, envie um objeto JSON vazio: {}.")
            self.respond_json(200, {"parando": True})
            self.wfile.flush()
            # shutdown precisa rodar fora da thread de serve_forever.
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def log_message(self, message, *args):
        LOGGER.info(message, *args)


def main():
    parser = argparse.ArgumentParser(description="Um quiz espacial de 30 perguntas para estudar Python e Docker.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8001")))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    server = Server((args.host, args.port))
    LOGGER.info("Orbit Dispatch: http://localhost:%s", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Central encerrada.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
