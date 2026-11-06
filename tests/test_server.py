import http.client
import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import server


class AccountAPITests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        server.DATABASE = Path(self.temp_dir.name) / "autonome-test.sqlite3"
        server.APP_SECRET = "test-secret-for-autonome"
        server.init_db()
        self.sent_codes = []
        self.original_sender = server.send_verification_email
        server.send_verification_email = lambda email, code, purpose: self.sent_codes.append((email, code, purpose))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.AutonoMeHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.httpd.server_address
        self.cookie = ""

    def tearDown(self):
        server.send_verification_email = self.original_sender
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
        self.temp_dir.cleanup()

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=5)
        headers = {"Host": f"{self.host}:{self.port}", "Origin": f"http://{self.host}:{self.port}"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw_body = response.read()
        try:
            result = json.loads(raw_body)
        except json.JSONDecodeError:
            result = raw_body.decode("utf-8", errors="replace")
        response_headers = response.getheaders()
        connection.close()
        for name, value in response_headers:
            if name.lower() == "set-cookie":
                self.cookie = value.split(";", 1)[0]
        return response.status, result

    def register(self):
        payload = {
            "name": "Pessoa Teste",
            "email": "pessoa@example.com",
            "cpf": "529.982.247-25",
            "phone": "(11) 98765-4321",
            "role": "both",
            "password": "senha-segura-123",
        }
        status, response = self.request("POST", "/api/auth/register/start", payload)
        self.assertEqual(status, 202, response)
        code = self.sent_codes[-1][1]
        self.assertRegex(code, re.compile(r"^[A-Z0-9]{6}$"))
        status, response = self.request("POST", "/api/auth/register/verify", {"email": payload["email"], "code": code})
        self.assertEqual(status, 200, response)
        return payload

    def test_registration_requires_email_code_and_creates_authenticated_user(self):
        payload = self.register()
        status, response = self.request("GET", "/api/auth/me")
        self.assertEqual(status, 200)
        self.assertEqual(response["user"]["email"], payload["email"])
        self.assertEqual(response["user"]["role"], "both")
        with server.database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM email_verifications").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users WHERE email = ?", (payload["email"],)).fetchone()[0], 1)
            self.assertNotIn("52998224725", json.dumps(dict(db.execute("SELECT * FROM users").fetchone())))

    def test_wrong_code_is_counted_and_email_delivery_failure_does_not_create_challenge(self):
        payload = {
            "name": "Pessoa Teste",
            "email": "pessoa@example.com",
            "cpf": "52998224725",
            "phone": "11987654321",
            "role": "client",
            "password": "senha-segura-123",
        }
        status, _ = self.request("POST", "/api/auth/register/start", payload)
        self.assertEqual(status, 202)
        status, response = self.request("POST", "/api/auth/register/verify", {"email": payload["email"], "code": "ZZZZZZ"})
        self.assertEqual(status, 400)
        self.assertIn("incorreto", response["error"])
        with server.database() as db:
            self.assertEqual(db.execute("SELECT attempts FROM email_verifications").fetchone()[0], 1)

        server.send_verification_email = lambda *_args: (_ for _ in ()).throw(RuntimeError("Email delivery is not configured."))
        status, response = self.request("POST", "/api/auth/register/start", {**payload, "email": "other@example.com"})
        self.assertEqual(status, 503)
        self.assertIn("SMTP_HOST", response["error"])
        self.assertIn("SMTP_PASSWORD", response["error"])
        self.assertIn("Free do Render", response["error"])
        self.assertIn("API HTTPS ainda não está integrado", response["error"])
        with server.database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM email_verifications WHERE email = 'other@example.com'").fetchone()[0], 0)

    def test_login_and_deactivation_move_account_to_disabled_table(self):
        payload = self.register()
        self.request("POST", "/api/auth/logout", {})
        self.cookie = ""
        status, _ = self.request("POST", "/api/auth/login", {"email": payload["email"], "password": payload["password"]})
        self.assertEqual(status, 200)
        status, _ = self.request("POST", "/api/auth/role", {"role": "provider"})
        self.assertEqual(status, 200)
        status, response = self.request("POST", "/api/auth/deactivate/start", {})
        self.assertEqual(status, 202, response)
        code = self.sent_codes[-1][1]
        status, response = self.request("POST", "/api/auth/deactivate/verify", {"code": code})
        self.assertEqual(status, 200, response)
        status, response = self.request("GET", "/api/auth/me")
        self.assertIsNone(response["user"])
        with server.database() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
            disabled = db.execute("SELECT * FROM disabled_users").fetchone()
            self.assertEqual(disabled["email"], payload["email"])
            self.assertEqual(disabled["role"], "provider")
            self.assertIsNotNone(disabled["disabled_at"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)

    def test_invalid_registration_data_is_rejected_before_email(self):
        payload = {
            "name": "Pessoa Teste",
            "email": "pessoa@example.com",
            "cpf": "12345678900",
            "phone": "00987654321",
            "role": "client",
            "password": "senha-segura-123",
        }
        status, _ = self.request("POST", "/api/auth/register/start", payload)
        self.assertEqual(status, 400)
        self.assertEqual(self.sent_codes, [])

    def test_verification_attempt_limit_and_disabled_email_reuse(self):
        payload = {
            "name": "Pessoa Teste",
            "email": "pessoa@example.com",
            "cpf": "52998224725",
            "phone": "11987654321",
            "role": "client",
            "password": "senha-segura-123",
        }
        status, _ = self.request("POST", "/api/auth/register/start", payload)
        self.assertEqual(status, 202)
        correct_code = self.sent_codes[-1][1]
        wrong_code = ("A" if correct_code[0] != "A" else "B") + correct_code[1:]
        for _ in range(server.OTP_MAX_ATTEMPTS):
            status, _ = self.request(
                "POST",
                "/api/auth/register/verify",
                {"email": payload["email"], "code": wrong_code},
            )
            self.assertEqual(status, 400)
        status, _ = self.request(
            "POST",
            "/api/auth/register/verify",
            {"email": payload["email"], "code": correct_code},
        )
        self.assertEqual(status, 429)

        payload["email"] = "another@example.com"
        status, _ = self.request("POST", "/api/auth/register/start", payload)
        self.assertEqual(status, 202)
        valid_code = self.sent_codes[-1][1]
        status, _ = self.request(
            "POST",
            "/api/auth/register/verify",
            {"email": payload["email"], "code": valid_code},
        )
        self.assertEqual(status, 200)
        self.request("POST", "/api/auth/deactivate/start", {})
        deactivate_code = self.sent_codes[-1][1]
        status, _ = self.request(
            "POST",
            "/api/auth/deactivate/verify",
            {"code": deactivate_code},
        )
        self.assertEqual(status, 200)
        status, response = self.request(
            "POST",
            "/api/auth/register/start",
            {**payload, "email": "another@example.com"},
        )
        self.assertEqual(status, 409)
        self.assertIn("Já existe", response["error"])

    def test_resend_code_rotates_challenge_and_enforces_cooldown(self):
        payload = {
            "name": "Pessoa Teste",
            "email": "pessoa@example.com",
            "cpf": "52998224725",
            "phone": "11987654321",
            "role": "client",
            "password": "senha-segura-123",
        }
        status, _ = self.request("POST", "/api/auth/register/start", payload)
        self.assertEqual(status, 202)
        first_code = self.sent_codes[-1][1]
        status, _ = self.request(
            "POST",
            "/api/auth/verification/resend",
            {"purpose": "register", "email": payload["email"]},
        )
        self.assertEqual(status, 429)
        with server.database() as db:
            db.execute("UPDATE email_verifications SET created_at = created_at - 61")
        status, _ = self.request(
            "POST",
            "/api/auth/verification/resend",
            {"purpose": "register", "email": payload["email"]},
        )
        self.assertEqual(status, 202)
        second_code = self.sent_codes[-1][1]
        self.assertNotEqual(first_code, second_code)
        status, _ = self.request(
            "POST",
            "/api/auth/register/verify",
            {"email": payload["email"], "code": first_code},
        )
        self.assertEqual(status, 400)
        status, response = self.request(
            "POST",
            "/api/auth/register/verify",
            {"email": payload["email"], "code": second_code},
        )
        self.assertEqual(status, 200, response)

    def test_server_does_not_serve_database_or_backend_source(self):
        status, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        status, _ = self.request("GET", "/server.py")
        self.assertEqual(status, 404)
        status, _ = self.request("GET", "/data/autonome.sqlite3")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
