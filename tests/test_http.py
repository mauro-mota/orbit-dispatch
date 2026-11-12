"""Conversa HTTP real em porta temporária; nunca encerra a central do usuário."""
import http.client
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile

from perguntas import PERGUNTAS
from server import Server, allowed_host


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = Server(("127.0.0.1", 0))
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=5)

    def request(self, method, path, payload=None, headers=None, raw=None, server=None):
        server = server or self.server
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        actual_headers = {"Content-Type": "application/json", "X-Dispatch-Token": server.token}
        actual_headers.update(headers or {})
        body = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        try:
            connection.request(method, path, body=body, headers=actual_headers)
            response = connection.getresponse()
            content = response.read()
            if content and response.getheader("Content-Type", "").startswith("application/json"):
                content = json.loads(content)
            return response.status, content, dict(response.getheaders())
        finally:
            connection.close()

    def test_saude_e_cabecalhos(self):
        status, data, headers = self.request("GET", "/api/saude")
        self.assertEqual((status, data), (200, {"status": "ok"}))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_arquivos_permitidos_e_token(self):
        # Arquivos de teste isolam o servidor do trabalho visual em andamento.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("<html>__DISPATCH_TOKEN__</html>")
            (root / "app.js").write_text("// JavaScript")
            (root / "styles.css").write_text("body {}")
            with patch("server.ROOT", root):
                for path, mime in [("/", "text/html"), ("/app.js", "text/javascript"), ("/styles.css", "text/css")]:
                    status, content, headers = self.request("GET", path)
                    self.assertEqual(status, 200)
                    self.assertTrue(headers["Content-Type"].startswith(mime))
                    if path == "/":
                        self.assertIn(self.server.token.encode(), content)
                        self.assertNotIn(b"__DISPATCH_TOKEN__", content)
                    head_status, body, head_headers = self.request("HEAD", path)
                    self.assertEqual(head_status, 200)
                    self.assertEqual(body, b"")
                    self.assertEqual(head_headers["Content-Length"], str(len(content)))

    def test_head_saude_e_rota_inexistente(self):
        for path, expected in [("/api/saude", 200), ("/inexistente", 404)]:
            status, body, headers = self.request("HEAD", path)
            self.assertEqual(status, expected)
            self.assertEqual(body, b"")
            self.assertGreater(int(headers["Content-Length"]), 0)

    def test_rodada_completa_e_retomada_por_http(self):
        status, jogo, _ = self.request("POST", "/api/jogo", {"respostas": []})
        self.assertEqual(status, 200)
        for pergunta in PERGUNTAS:
            self.assertEqual(jogo["pergunta"]["id"], pergunta["id"])
            self.assertNotIn("correta", jogo["pergunta"])
            payload = {"respostas": jogo["respostas"], "pergunta": pergunta["id"], "escolha": pergunta["correta"]}
            status, jogo, _ = self.request("POST", "/api/responder", payload)
            self.assertEqual(status, 200)
            self.assertEqual(self.request("POST", "/api/responder", payload)[1], jogo)
            self.assertEqual(self.request("POST", "/api/jogo", {"respostas": jogo["respostas"]})[1], jogo)
        self.assertEqual(jogo["acertos"], 30)
        self.assertEqual(jogo["respondidas"], 30)
        self.assertTrue(jogo["concluido"])
        self.assertIsNone(jogo["pergunta"])
        self.assertEqual(self.request("POST", "/api/responder", {"respostas": jogo["respostas"], "pergunta": "p30", "escolha": "a"})[0], 422)

    def test_erros_json_e_validacao(self):
        for raw in [b"{broken", b"{\"a\": NaN}", b"\xff"]:
            self.assertEqual(self.request("POST", "/api/responder", raw=raw)[0], 400)
        for payload in [{}, [], True, {"respostas": [], "pergunta": "p01", "escolha": "c"}]:
            self.assertEqual(self.request("POST", "/api/responder", payload)[0], 422)

    def test_tipo_tamanho_e_transferencia(self):
        self.assertEqual(self.request("POST", "/api/responder", {}, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/responder", {}, {"Content-Length": "abc"})[0], 400)
        self.assertEqual(self.request("POST", "/api/responder", {}, {"Transfer-Encoding": "chunked"})[0], 400)
        self.assertEqual(self.request("POST", "/api/responder", raw=b"")[0], 413)
        self.assertEqual(self.request("POST", "/api/responder", {"x": "a" * 4096})[0], 413)

    def test_rotas_nao_expoem_arquivos(self):
        for path in ["/server.py", "/casos.py", "/perguntas.py", "/api/chamado", "/../server.py", "/%2e%2e/server.py", "/characters/lia.png"]:
            self.assertEqual(self.request("GET", path)[0], 404)
        self.assertEqual(self.request("POST", "/api/antiga", {})[0], 404)
        self.assertEqual(self.request("POST", "/api/resolver", {})[0], 404)

    def test_host_token_e_origem(self):
        self.assertEqual(self.request("GET", "/api/saude", headers={"Host": "evil.example:8001"})[0], 403)
        for path in ["/api/jogo", "/api/responder", "/api/parar"]:
            for token in ["", "wrong", "é"]:
                self.assertEqual(self.request("POST", path, {}, {"X-Dispatch-Token": token})[0], 403)
            self.assertEqual(self.request("POST", path, {}, {"Origin": "https://example.com"})[0], 403)
        payload = {"respostas": [], "pergunta": "p01", "escolha": "a"}
        origin = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("POST", "/api/responder", payload, {"Origin": origin})[0], 200)

    def test_validacao_de_hosts(self):
        for host in ["localhost:8001", "127.0.0.1:8000", "[::1]:8001"]:
            self.assertTrue(allowed_host(host))
        for host in ["", "localhost", "evil.example:8001", "localhost.evil:8001", "user@localhost:8001", "localhost:bad", "localhost:8001/path"]:
            self.assertFalse(allowed_host(host))

    def test_parar_encerra_apenas_servidor_isolado(self):
        isolated = Server(("127.0.0.1", 0))
        worker = threading.Thread(target=isolated.serve_forever, daemon=True)
        worker.start()
        try:
            self.assertEqual(self.request("POST", "/api/parar", {"extra": True}, server=isolated)[0], 422)
            status, data, _ = self.request("POST", "/api/parar", {}, server=isolated)
            self.assertEqual((status, data), (200, {"parando": True}))
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(self.request("GET", "/api/saude")[0], 200)
        finally:
            isolated.shutdown()
            isolated.server_close()
            worker.join(timeout=3)
