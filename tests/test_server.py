import http.client
import json
import os
import re
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path
import server


class EmailDeliveryTests(unittest.TestCase):
    @patch.dict(os.environ, {
        "BREVO_API_KEY": "test-api-key",
        "EMAIL_FROM": "verified@example.com",
        "EMAIL_FROM_NAME": "AutonoMe Test",
    }, clear=True)
    @patch("server.urllib.request.urlopen")
    def test_brevo_api_sends_verification_message_over_https(self, urlopen):
        server.send_verification_email("customer@example.com", "A1B2C3", "register")

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(request.get_header("Api-key"), "test-api-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["sender"], {"name": "AutonoMe Test", "email": "verified@example.com"})
        self.assertEqual(payload["to"], [{"email": "customer@example.com"}])
        self.assertIn("A1B2C3", payload["textContent"])
        urlopen.assert_called_once_with(request, timeout=15)


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
        except (json.JSONDecodeError, UnicodeDecodeError):
            result = raw_body.decode("utf-8", errors="replace")
        response_headers = response.getheaders()
        connection.close()
        for name, value in response_headers:
            if name.lower() == "set-cookie":
                self.cookie = value.split(";", 1)[0]
        return response.status, result

    def register_account(self, email="pessoa@example.com", name="Pessoa Teste", role="both"):
        payload = {
            "name": name,
            "email": email,
            "cpf": "529.982.247-25",
            "phone": "(11) 98765-4321",
            "role": role,
            "password": "senha-segura-123",
        }
        status, response = self.request("POST", "/api/auth/register/start", payload)
        self.assertEqual(status, 202, response)
        code = self.sent_codes[-1][1]
        self.assertRegex(code, re.compile(r"^[A-Z0-9]{6}$"))
        status, response = self.request("POST", "/api/auth/register/verify", {"email": payload["email"], "code": code})
        self.assertEqual(status, 200, response)
        return payload

    def register(self):
        return self.register_account()

    def test_real_listings_and_hiring_requests_are_shared_between_accounts(self):
        customer = {
            "name": "Cliente Teste",
            "email": "cliente@example.com",
            "cpf": "529.982.247-25",
            "phone": "(11) 98765-4321",
            "role": "client",
            "password": "senha-segura-123",
        }
        self.assertEqual(self.request("POST", "/api/auth/register/start", customer)[0], 202)
        status, _ = self.request(
            "POST",
            "/api/auth/register/verify",
            {"email": customer["email"], "code": self.sent_codes[-1][1]},
        )
        self.assertEqual(status, 200)
        customer_cookie = self.cookie

        self.cookie = ""
        worker = self.register()
        worker_cookie = self.cookie
        worker_id = self.request("GET", "/api/auth/me")[1]["user"]["id"]
        listing_payload = {
            "category": "Reparos e Assistência",
            "service": "Conserto de bicicletas",
            "location": "São Paulo, SP",
            "price": "A combinar",
            "about": "Faço manutenção de bicicletas em domicílio.",
        }
        status, response = self.request("POST", "/api/listings", listing_payload)
        self.assertEqual(status, 201, response)
        listing_id = response["listing"]["id"]
        self.assertEqual(response["user"]["role"], "both")
        self.assertNotIn("email", response["listing"])
        self.assertNotIn("phone", response["listing"])

        self.cookie = customer_cookie
        status, response = self.request("GET", "/api/listings")
        self.assertEqual(status, 200)
        self.assertEqual(len(response["listings"]), 1)
        self.assertEqual(response["listings"][0]["ownerId"], worker_id)
        self.assertFalse(response["listings"][0]["isBooked"])
        self.assertNotIn("email", json.dumps(response))
        self.assertNotIn("phone", json.dumps(response))

        status, response = self.request(
            "POST",
            "/api/contracts",
            {"listingId": listing_id, "date": "Seg, 20/05 às 10:00", "details": "Preciso ajustar os freios."},
        )
        self.assertEqual(status, 201, response)
        contract_id = response["contract"]["id"]
        self.assertEqual(response["contract"]["tab"], "requested")
        self.assertEqual(response["contract"]["name"], worker["name"])
        self.assertTrue(self.request("GET", "/api/listings")[1]["listings"][0]["isBooked"])
        self.assertEqual(self.request("POST", "/api/contracts", {"listingId": listing_id, "date": "Ter, 21/05 às 10:00"})[0], 409)
        self.assertEqual(
            self.request("POST", f"/api/contracts/{contract_id}/status", {"status": "confirm"})[0],
            403,
        )
        self.assertEqual(self.request("DELETE", f"/api/listings/{listing_id}")[0], 404)

        self.cookie = worker_cookie
        status, response = self.request("GET", "/api/contracts")
        self.assertEqual(status, 200)
        self.assertEqual(response["contracts"][0]["tab"], "hired")
        self.assertEqual(response["contracts"][0]["name"], customer["name"])
        self.assertEqual(response["contracts"][0]["details"], "Preciso ajustar os freios.")
        status, response = self.request(
            "POST",
            f"/api/contracts/{contract_id}/status",
            {"status": "confirm"},
        )
        self.assertEqual(status, 200, response)
        self.assertEqual(response["contract"]["state"], "Confirmado")
        self.cookie = customer_cookie
        status, response = self.request(
            "POST",
            f"/api/contracts/{contract_id}/status",
            {"status": "cancel"},
        )
        self.assertEqual(status, 200, response)
        self.assertEqual(response["contract"]["state"], "Cancelada")
        self.assertFalse(self.request("GET", "/api/listings")[1]["listings"][0]["isBooked"])

        self.cookie = worker_cookie
        self.assertEqual(self.request("DELETE", f"/api/listings/{listing_id}")[0], 200)
        self.assertEqual(self.request("GET", "/api/listings")[1]["listings"], [])

    def test_marketplace_endpoints_require_an_account(self):
        status, response = self.request("GET", "/api/listings")
        self.assertEqual(status, 401)
        self.assertIn("Entre na sua conta", response["error"])
        status, response = self.request("GET", "/api/contracts")
        self.assertEqual(status, 401)
        self.assertIn("Entre na sua conta", response["error"])

    def test_profile_and_listing_can_be_updated_by_their_owner(self):
        self.register()
        listing = {
            "category": "Reparos e Assistência",
            "service": "Conserto de bicicletas",
            "location": "São Paulo, SP",
            "price": "A combinar",
            "about": "Manutenção em domicílio.",
        }
        status, response = self.request("POST", "/api/listings", listing)
        self.assertEqual(status, 201, response)
        listing_id = response["listing"]["id"]

        status, response = self.request("POST", "/api/auth/profile", {
            "name": "Nome atualizado",
            "profileBio": "Faço serviços com cuidado.",
            "profileLocation": "Santo André, SP",
            "profilePhoto": "data:image/jpeg;base64,/9h4/9k=",
        })
        self.assertEqual(status, 200, response)
        self.assertEqual(response["user"]["name"], "Nome atualizado")
        self.assertEqual(response["user"]["profileBio"], "Faço serviços com cuidado.")
        self.assertEqual(response["user"]["profileLocation"], "Santo André, SP")
        self.assertEqual(response["user"]["profilePhoto"], "data:image/jpeg;base64,/9h4/9k=")

        status, response = self.request("POST", f"/api/listings/{listing_id}", {
            **listing,
            "service": "Revisão de bicicletas",
            "price": "R$ 80",
        })
        self.assertEqual(status, 200, response)
        self.assertEqual(response["listing"]["service"], "Revisão de bicicletas")
        self.assertEqual(response["listing"]["name"], "Nome atualizado")
        self.assertEqual(response["listing"]["profileBio"], "Faço serviços com cuidado.")
        self.assertEqual(response["listing"]["profileLocation"], "Santo André, SP")
        self.assertEqual(response["listing"]["profilePhoto"], "data:image/jpeg;base64,/9h4/9k=")

        self.register_account("cliente@example.com", "Cliente")
        status, response = self.request("POST", f"/api/listings/{listing_id}", listing)
        self.assertEqual(status, 404, response)
        status, response = self.request("POST", "/api/auth/profile", {"name": "x" * 121})
        self.assertEqual(status, 400, response)
        status, response = self.request("POST", "/api/auth/profile", {
            "name": "Cliente",
            "profilePhoto": "data:image/png;base64,Zm9v",
        })
        self.assertEqual(status, 400, response)

    def test_contract_chat_is_shared_and_restricted_to_participants(self):
        self.register_account("worker@example.com", "Profissional")
        worker_cookie = self.cookie
        listing_payload = {
            "category": "Reparos e Assistência",
            "service": "Conserto de bicicletas",
            "location": "São Paulo, SP",
            "price": "A combinar",
            "about": "Manutenção em domicílio.",
        }
        _, listing_response = self.request("POST", "/api/listings", listing_payload)
        listing_id = listing_response["listing"]["id"]

        self.cookie = ""
        self.register_account("customer@example.com", "Contratante", "client")
        customer_cookie = self.cookie
        status, response = self.request("POST", "/api/contracts", {
            "listingId": listing_id,
            "date": "Segunda às 10:00",
        })
        self.assertEqual(status, 201, response)
        contract_id = response["contract"]["id"]

        status, response = self.request("GET", "/api/messages")
        self.assertEqual(status, 200, response)
        self.assertEqual(response["conversations"][0]["contractId"], contract_id)
        self.assertEqual(response["conversations"][0]["unreadCount"], 0)
        status, response = self.request("POST", "/api/messages", {
            "contractId": contract_id,
            "body": "Olá, podemos combinar os detalhes?",
        })
        self.assertEqual(status, 201, response)
        self.assertTrue(response["message"]["mine"])

        self.cookie = worker_cookie
        status, response = self.request("GET", f"/api/messages?contractId={contract_id}")
        self.assertEqual(status, 200, response)
        self.assertEqual(response["messages"][0]["body"], "Olá, podemos combinar os detalhes?")
        self.assertFalse(response["messages"][0]["mine"])
        status, response = self.request("POST", "/api/messages", {
            "contractId": contract_id,
            "body": "Claro, pode me contar mais?",
        })
        self.assertEqual(status, 201, response)

        self.cookie = ""
        self.register_account("intruso@example.com", "Terceiro", "client")
        status, response = self.request("GET", f"/api/messages?contractId={contract_id}")
        self.assertEqual(status, 404, response)
        status, response = self.request("POST", "/api/messages", {
            "contractId": contract_id,
            "body": "Mensagem não autorizada",
        })
        self.assertEqual(status, 404, response)

        self.cookie = customer_cookie
        status, response = self.request("POST", f"/api/contracts/{contract_id}/status", {"status": "cancel"})
        self.assertEqual(status, 200, response)
        status, response = self.request("GET", f"/api/messages?contractId={contract_id}")
        self.assertEqual(status, 404, response)

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
        self.assertIn("Render Free", response["error"])
        self.assertIn("BREVO_API_KEY", response["error"])
        self.assertIn("EMAIL_FROM", response["error"])
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
        status, _ = self.request("GET", "/logo_autonome.png")
        self.assertEqual(status, 200)
        status, _ = self.request("GET", "/server.py")
        self.assertEqual(status, 404)
        status, _ = self.request("GET", "/data/autonome.sqlite3")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
