import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import string
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("AUTONOME_DB_PATH", ROOT / "data" / "autonome.sqlite3"))
APP_ENV = os.environ.get("APP_ENV", "development")
APP_SECRET = os.environ.get("APP_SECRET")
if APP_ENV == "production" and not APP_SECRET:
    raise RuntimeError("APP_SECRET must be set when APP_ENV=production.")
if APP_ENV == "production" and len(APP_SECRET) < 32:
    raise RuntimeError("APP_SECRET must contain at least 32 characters in production.")
if APP_ENV == "production" and os.environ.get("COOKIE_SECURE", "").lower() != "true":
    raise RuntimeError("COOKIE_SECURE=true is required when APP_ENV=production.")
if not APP_SECRET:
    APP_SECRET = secrets.token_hex(32)
    print("Warning: using a temporary development secret; sessions and pending codes expire after restart.", file=sys.stderr)

OTP_LIFETIME_SECONDS = 10 * 60
SESSION_LIFETIME_SECONDS = 30 * 24 * 60 * 60
OTP_MAX_ATTEMPTS = 5
OTP_ALPHABET = string.ascii_uppercase + string.digits
VALID_DDDS = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "21", "22", "24", "27", "28",
    "31", "32", "33", "34", "35", "37", "38", "41", "42", "43", "44", "45", "46", "47",
    "48", "49", "51", "53", "54", "55", "61", "62", "63", "64", "65", "66", "67", "68",
    "69", "71", "73", "74", "75", "77", "79", "81", "82", "83", "84", "85", "86", "87",
    "88", "89", "91", "92", "93", "94", "95", "96", "97", "98", "99",
}


class APIError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def connect_db():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database():
    connection = connect_db()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    with database() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('client', 'provider', 'both')),
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS disabled_users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT NOT NULL,
                role TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                disabled_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS email_verifications (
                id TEXT PRIMARY KEY,
                purpose TEXT NOT NULL CHECK (purpose IN ('register', 'deactivate')),
                email TEXT NOT NULL COLLATE NOCASE,
                user_id TEXT,
                payload TEXT,
                code_hash TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS email_verifications_lookup
                ON email_verifications(email, purpose, created_at);
            CREATE INDEX IF NOT EXISTS sessions_user_lookup ON sessions(user_id);
            """
        )


def only_digits(value):
    return "".join(character for character in value if character in string.digits)


def valid_cpf(value):
    cpf = only_digits(value)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    def digit_for(length):
        total = sum(int(cpf[index]) * (length + 1 - index) for index in range(length))
        remainder = (total * 10) % 11
        return 0 if remainder == 10 else remainder

    return digit_for(9) == int(cpf[9]) and digit_for(10) == int(cpf[10])


def valid_brazilian_phone(value):
    phone = only_digits(value)
    return (
        len(phone) == 11
        and phone[:2] in VALID_DDDS
        and phone[2] == "9"
    )


def hash_password(password, salt=None):
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 310_000)
    return salt_bytes.hex(), password_hash.hex()


def verification_hash(code):
    return hmac.new(APP_SECRET.encode("utf-8"), code.encode("ascii"), hashlib.sha256).hexdigest()


def send_verification_email(address, code, purpose):
    host = os.environ.get("SMTP_HOST")
    sender = os.environ.get("SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("Email delivery is not configured. Set SMTP_HOST and SMTP_FROM.")

    is_registration = purpose == "register"
    message = EmailMessage()
    message["Subject"] = "Confirme seu cadastro no AutonoMe" if is_registration else "Confirme a desativação da sua conta AutonoMe"
    message["From"] = sender
    message["To"] = address
    action = "concluir seu cadastro" if is_registration else "desativar sua conta"
    message.set_content(
        f"Use este código para {action} no AutonoMe:\n\n"
        f"{code}\n\n"
        f"O código expira em 10 minutos. Se você não solicitou esta ação, ignore esta mensagem."
    )

    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    if os.environ.get("SMTP_USE_SSL", "").lower() == "true":
        with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if os.environ.get("SMTP_STARTTLS", "true").lower() == "true":
            smtp.starttls()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(message)


def create_verification(db, email, purpose, payload=None, user_id=None):
    now = int(time.time())
    recent = db.execute(
        """SELECT created_at FROM email_verifications
           WHERE email = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1""",
        (email, purpose),
    ).fetchone()
    if recent and now - recent["created_at"] < 60:
        raise APIError(HTTPStatus.TOO_MANY_REQUESTS, "Aguarde 1 minuto antes de solicitar outro código.")
    code = "".join(secrets.choice(OTP_ALPHABET) for _ in range(6))
    challenge_id = str(uuid.uuid4())
    db.execute(
        "DELETE FROM email_verifications WHERE email = ? AND purpose = ?",
        (email, purpose),
    )
    db.execute(
        """INSERT INTO email_verifications
           (id, purpose, email, user_id, payload, code_hash, expires_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            challenge_id,
            purpose,
            email,
            user_id,
            json.dumps(payload) if payload is not None else None,
            verification_hash(code),
            now + OTP_LIFETIME_SECONDS,
            now,
        ),
    )
    return challenge_id, code


def establish_session(db, user_id):
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, now + SESSION_LIFETIME_SECONDS, now),
    )
    return token


def public_user(user):
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}


class AutonoMeHandler(SimpleHTTPRequestHandler):
    server_version = "AutonoMe/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_json(self, status, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        if self.headers.get_content_type() != "application/json":
            raise APIError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Envie os dados no formato JSON.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise APIError(HTTPStatus.BAD_REQUEST, "Requisição inválida.") from error
        if length < 1 or length > 16_384:
            raise APIError(HTTPStatus.BAD_REQUEST, "Tamanho de requisição inválido.")
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise APIError(HTTPStatus.BAD_REQUEST, "Dados inválidos.") from error
        if not isinstance(payload, dict):
            raise APIError(HTTPStatus.BAD_REQUEST, "Dados inválidos.")
        return payload

    def get_session_user(self, db):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("autonome_session")
        if not morsel:
            return None
        token_hash = hashlib.sha256(morsel.value.encode("ascii", "ignore")).hexdigest()
        row = db.execute(
            """SELECT users.* FROM sessions
               JOIN users ON users.id = sessions.user_id
               WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
            (token_hash, int(time.time())),
        ).fetchone()
        return row

    def session_cookie(self, token, max_age):
        secure = os.environ.get("COOKIE_SECURE", "").lower() == "true"
        parts = [
            f"autonome_session={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Strict",
            f"Max-Age={max_age}",
        ]
        if secure:
            parts.append("Secure")
        return ("Set-Cookie", "; ".join(parts))

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path == "/api/auth/me":
            with database() as db:
                user = self.get_session_user(db)
            if user is None:
                self.send_json(HTTPStatus.OK, {"user": None})
            else:
                self.send_json(HTTPStatus.OK, {"user": public_user(user)})
            return
        if request_path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint não encontrado."})
            return
        allowed_files = {
            "index.html", "style.css", "app.js", "manifest.webmanifest", "icon.svg",
            "icon-192.png", "icon-512.png", "apple-touch-icon.png", "service-worker.js",
        }
        asset = request_path.lstrip("/")
        if asset in {"", "."}:
            self.path = "/index.html"
        elif asset not in allowed_files:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint não encontrado."})
            return
        try:
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                raise APIError(HTTPStatus.FORBIDDEN, "Origem da requisição não autorizada.")
            payload = self.read_json()
            status, response, headers = self.handle_api(self.path, payload)
            self.send_json(status, response, headers)
        except APIError as error:
            self.send_json(error.status, {"error": str(error)})
        except Exception:
            self.log_error("Unhandled API error:\n%s", traceback.format_exc())
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Não foi possível concluir a solicitação. Tente novamente."})

    def handle_api(self, path, payload):
        if path == "/api/auth/register/start":
            return self.start_registration(payload)
        if path == "/api/auth/register/verify":
            return self.verify_registration(payload)
        if path == "/api/auth/verification/resend":
            return self.resend_verification(payload)
        if path == "/api/auth/login":
            return self.login(payload)
        if path == "/api/auth/role":
            return self.update_role(payload)
        if path == "/api/auth/logout":
            return self.logout()
        if path == "/api/auth/deactivate/start":
            return self.start_deactivation()
        if path == "/api/auth/deactivate/verify":
            return self.verify_deactivation(payload)
        raise APIError(HTTPStatus.NOT_FOUND, "Endpoint não encontrado.")

    def start_registration(self, payload):
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        phone = only_digits(str(payload.get("phone", "")))
        cpf = str(payload.get("cpf", ""))
        role = str(payload.get("role", "client"))
        password = str(payload.get("password", ""))
        if not name or len(name) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe seu nome.")
        if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe um e-mail válido.")
        if not valid_cpf(cpf):
            raise APIError(HTTPStatus.BAD_REQUEST, "O CPF informado é inválido.")
        if not valid_brazilian_phone(phone):
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe um celular brasileiro válido com DDD.")
        if role not in {"client", "provider", "both"}:
            raise APIError(HTTPStatus.BAD_REQUEST, "Selecione um perfil válido.")
        if len(password) < 8 or len(password) > 128:
            raise APIError(HTTPStatus.BAD_REQUEST, "A senha deve ter entre 8 e 128 caracteres.")

        with database() as db:
            existing = db.execute(
                "SELECT 1 FROM users WHERE email = ? UNION SELECT 1 FROM disabled_users WHERE email = ?",
                (email, email),
            ).fetchone()
            if existing:
                raise APIError(HTTPStatus.CONFLICT, "Já existe uma conta associada a este e-mail.")
            salt, password_hash = hash_password(password)
            challenge_id, code = create_verification(
                db,
                email,
                "register",
                {"name": name, "phone": phone, "role": role, "password_salt": salt, "password_hash": password_hash},
            )
        try:
            send_verification_email(email, code, "register")
        except Exception as error:
            with database() as db:
                db.execute("DELETE FROM email_verifications WHERE id = ?", (challenge_id,))
            if "not configured" in str(error).lower():
                raise APIError(HTTPStatus.SERVICE_UNAVAILABLE, "O envio de e-mail ainda não está configurado no servidor.") from error
            self.log_error("Email delivery failed for registration: %s", error)
            raise APIError(HTTPStatus.BAD_GATEWAY, "Não foi possível enviar o código. Confira o e-mail ou tente novamente.") from error
        return HTTPStatus.ACCEPTED, {"message": "Código enviado para o e-mail informado."}, []

    def consume_verification(self, db, email, purpose, code):
        row = db.execute(
            """SELECT * FROM email_verifications
               WHERE email = ? AND purpose = ? ORDER BY created_at DESC LIMIT 1""",
            (email, purpose),
        ).fetchone()
        now = int(time.time())
        if row is None or row["expires_at"] <= now:
            if row is not None:
                db.execute("DELETE FROM email_verifications WHERE id = ?", (row["id"],))
                db.commit()
            raise APIError(HTTPStatus.GONE, "O código expirou. Solicite um novo código.")
        if row["attempts"] >= OTP_MAX_ATTEMPTS:
            db.execute("DELETE FROM email_verifications WHERE id = ?", (row["id"],))
            db.commit()
            raise APIError(HTTPStatus.TOO_MANY_REQUESTS, "Limite de tentativas atingido. Solicite um novo código.")
        if not hmac.compare_digest(row["code_hash"], verification_hash(code)):
            db.execute("UPDATE email_verifications SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
            db.commit()
            raise APIError(HTTPStatus.BAD_REQUEST, "Código incorreto.")
        db.execute("DELETE FROM email_verifications WHERE id = ?", (row["id"],))
        return row

    def resend_verification(self, payload):
        purpose = str(payload.get("purpose", ""))
        with database() as db:
            if purpose == "register":
                email = str(payload.get("email", "")).strip().lower()
                existing = db.execute(
                    """SELECT payload FROM email_verifications
                       WHERE email = ? AND purpose = 'register' ORDER BY created_at DESC LIMIT 1""",
                    (email,),
                ).fetchone()
                if existing is None:
                    raise APIError(HTTPStatus.GONE, "Não há cadastro aguardando confirmação para este e-mail.")
                account = json.loads(existing["payload"])
                challenge_id, code = create_verification(db, email, purpose, account)
            elif purpose == "deactivate":
                user = self.get_session_user(db)
                if user is None:
                    raise APIError(HTTPStatus.UNAUTHORIZED, "Entre na sua conta para continuar.")
                existing = db.execute(
                    """SELECT 1 FROM email_verifications
                       WHERE email = ? AND purpose = 'deactivate' AND user_id = ? LIMIT 1""",
                    (user["email"], user["id"]),
                ).fetchone()
                if existing is None:
                    raise APIError(HTTPStatus.GONE, "Não há desativação aguardando confirmação.")
                email = user["email"]
                challenge_id, code = create_verification(db, email, purpose, user_id=user["id"])
            else:
                raise APIError(HTTPStatus.BAD_REQUEST, "Solicitação de código inválida.")
        try:
            send_verification_email(email, code, purpose)
        except Exception as error:
            with database() as db:
                db.execute("DELETE FROM email_verifications WHERE id = ?", (challenge_id,))
            if "not configured" in str(error).lower():
                raise APIError(HTTPStatus.SERVICE_UNAVAILABLE, "O envio de e-mail ainda não está configurado no servidor.") from error
            self.log_error("Email delivery failed for verification resend: %s", error)
            raise APIError(HTTPStatus.BAD_GATEWAY, "Não foi possível enviar o código. Tente novamente.") from error
        return HTTPStatus.ACCEPTED, {"message": "Enviamos um novo código para o e-mail."}, []

    def verify_registration(self, payload):
        email = str(payload.get("email", "")).strip().lower()
        code = str(payload.get("code", "")).strip().upper()
        if len(code) != 6 or any(character not in OTP_ALPHABET for character in code):
            raise APIError(HTTPStatus.BAD_REQUEST, "Digite o código de 6 letras e números.")
        with database() as db:
            challenge = self.consume_verification(db, email, "register", code)
            account = json.loads(challenge["payload"])
            user_id = str(uuid.uuid4())
            now = int(time.time())
            db.execute(
                """INSERT INTO users
                   (id, name, email, phone, role, password_salt, password_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    account["name"],
                    email,
                    account["phone"],
                    account["role"],
                    account["password_salt"],
                    account["password_hash"],
                    now,
                ),
            )
            user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            token = establish_session(db, user_id)
        return HTTPStatus.OK, {"user": public_user(user)}, [self.session_cookie(token, SESSION_LIFETIME_SECONDS)]

    def login(self, payload):
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        with database() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if user is None:
                raise APIError(HTTPStatus.UNAUTHORIZED, "E-mail ou senha incorretos.")
            _, password_hash = hash_password(password, user["password_salt"])
            if not hmac.compare_digest(user["password_hash"], password_hash):
                raise APIError(HTTPStatus.UNAUTHORIZED, "E-mail ou senha incorretos.")
            token = establish_session(db, user["id"])
        return HTTPStatus.OK, {"user": public_user(user)}, [self.session_cookie(token, SESSION_LIFETIME_SECONDS)]

    def update_role(self, payload):
        role = str(payload.get("role", ""))
        if role not in {"client", "provider", "both"}:
            raise APIError(HTTPStatus.BAD_REQUEST, "Selecione um perfil válido.")
        with database() as db:
            user = self.get_session_user(db)
            if user is None:
                raise APIError(HTTPStatus.UNAUTHORIZED, "Entre na sua conta para continuar.")
            db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user["id"]))
            updated_user = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        return HTTPStatus.OK, {"user": public_user(updated_user)}, []

    def logout(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("autonome_session")
        if morsel:
            token_hash = hashlib.sha256(morsel.value.encode("ascii", "ignore")).hexdigest()
            with database() as db:
                db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
        return HTTPStatus.OK, {"message": "Sessão encerrada."}, [self.session_cookie("", 0)]

    def start_deactivation(self):
        with database() as db:
            user = self.get_session_user(db)
            if user is None:
                raise APIError(HTTPStatus.UNAUTHORIZED, "Entre na sua conta para continuar.")
            challenge_id, code = create_verification(db, user["email"], "deactivate", user_id=user["id"])
        try:
            send_verification_email(user["email"], code, "deactivate")
        except Exception as error:
            with database() as db:
                db.execute("DELETE FROM email_verifications WHERE id = ?", (challenge_id,))
            if "not configured" in str(error).lower():
                raise APIError(HTTPStatus.SERVICE_UNAVAILABLE, "O envio de e-mail ainda não está configurado no servidor.") from error
            self.log_error("Email delivery failed for account deactivation: %s", error)
            raise APIError(HTTPStatus.BAD_GATEWAY, "Não foi possível enviar o código. Tente novamente.") from error
        return HTTPStatus.ACCEPTED, {"message": "Código enviado para o e-mail da conta."}, []

    def verify_deactivation(self, payload):
        code = str(payload.get("code", "")).strip().upper()
        if len(code) != 6 or any(character not in OTP_ALPHABET for character in code):
            raise APIError(HTTPStatus.BAD_REQUEST, "Digite o código de 6 letras e números.")
        with database() as db:
            user = self.get_session_user(db)
            if user is None:
                raise APIError(HTTPStatus.UNAUTHORIZED, "Entre na sua conta para continuar.")
            challenge = self.consume_verification(db, user["email"], "deactivate", code)
            if challenge["user_id"] != user["id"]:
                raise APIError(HTTPStatus.BAD_REQUEST, "O código não corresponde à conta atual.")
            now = int(time.time())
            db.execute(
                """INSERT INTO disabled_users
                   (id, name, email, phone, role, password_salt, password_hash, created_at, disabled_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user["id"],
                    user["name"],
                    user["email"],
                    user["phone"],
                    user["role"],
                    user["password_salt"],
                    user["password_hash"],
                    user["created_at"],
                    now,
                ),
            )
            db.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        return HTTPStatus.OK, {"message": "Conta desativada."}, [self.session_cookie("", 0)]


def main():
    init_db()
    default_host = "0.0.0.0" if APP_ENV == "production" else "127.0.0.1"
    host = os.environ.get("AUTONOME_HOST", default_host)
    port = int(os.environ.get("PORT", os.environ.get("AUTONOME_PORT", "8000")))
    server = ThreadingHTTPServer((host, port), AutonoMeHandler)
    print(f"AutonoMe running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAutonoMe stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
