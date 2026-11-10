import hashlib
import hmac
import base64
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
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


DATABASE_INTEGRITY_ERRORS = (sqlite3.IntegrityError,) + (
    (psycopg.IntegrityError,) if psycopg is not None else ()
)

ROOT = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("AUTONOME_DB_PATH", ROOT / "data" / "autonome.sqlite3"))
DATABASE_URL = os.environ.get("DATABASE_URL")
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
MAX_JSON_BODY_BYTES = 1_000_000
MAX_PROFILE_PHOTO_BYTES = 300_000
SMTP_NOT_CONFIGURED_MESSAGE = (
    "O envio de e-mail não está configurado. No Render Free, configure BREVO_API_KEY e "
    "EMAIL_FROM em Environment usando um remetente verificado no Brevo. Em outra hospedagem, "
    "também é possível usar SMTP com SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD e SMTP_FROM."
)
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


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=()):
        return self.connection.execute(statement.replace("?", "%s"), parameters)

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def close(self):
        self.connection.close()

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback_value):
        return self.connection.__exit__(exc_type, exc_value, traceback_value)


def connect_db():
    if DATABASE_URL:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL requires psycopg. Install the project requirements.")
        return PostgresConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10))

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


def table_columns(db, table_name):
    if DATABASE_URL:
        return {
            row["column_name"]
            for row in db.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = ?",
                (table_name,),
            )
        }
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table_name})")}


def init_db():
    if APP_ENV == "production" and not DATABASE_URL:
        print(
            "Warning: DATABASE_URL is unset; Render Free SQLite storage is ephemeral and may be lost.",
            file=sys.stderr,
        )
    with database() as db:
        schema = """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                phone TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('client', 'provider', 'both')),
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                profile_bio TEXT NOT NULL DEFAULT '',
                profile_location TEXT NOT NULL DEFAULT '',
                profile_photo TEXT NOT NULL DEFAULT ''
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
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category TEXT NOT NULL,
                service TEXT NOT NULL,
                location TEXT NOT NULL,
                price TEXT NOT NULL,
                about TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contracts (
                id TEXT PRIMARY KEY,
                listing_id TEXT REFERENCES listings(id) ON DELETE SET NULL,
                client_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                service TEXT NOT NULL,
                date TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                service_date TEXT,
                service_time TEXT,
                service_address TEXT NOT NULL DEFAULT '',
                state TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS availability (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
                service_time TEXT NOT NULL,
                PRIMARY KEY (user_id, weekday, service_time)
            );
            CREATE TABLE IF NOT EXISTS favorites (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                listing_id TEXT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, listing_id)
            );
            CREATE TABLE IF NOT EXISTS contract_notes (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                contract_id TEXT REFERENCES contracts(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS contract_notes_user_lookup
                ON contract_notes(contract_id, user_id, created_at);
            CREATE INDEX IF NOT EXISTS notifications_user_lookup
                ON notifications(user_id, created_at);
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
                sender_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                read_at INTEGER
            );
            CREATE INDEX IF NOT EXISTS email_verifications_lookup
                ON email_verifications(email, purpose, created_at);
            CREATE INDEX IF NOT EXISTS sessions_user_lookup ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS listings_public_lookup ON listings(active, category, service);
            CREATE INDEX IF NOT EXISTS contracts_client_lookup ON contracts(client_id, created_at);
            CREATE INDEX IF NOT EXISTS contracts_provider_lookup ON contracts(provider_id, created_at);
            CREATE INDEX IF NOT EXISTS messages_conversation_lookup ON messages(contract_id, created_at);
            CREATE INDEX IF NOT EXISTS messages_inbox_lookup ON messages(recipient_id, read_at, created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS contracts_one_active_per_listing
                ON contracts(listing_id)
                WHERE listing_id IS NOT NULL AND state IN ('Aguardando confirmação', 'Confirmado');
            """
        if DATABASE_URL:
            schema = schema.replace(" COLLATE NOCASE", "")
        db.executescript(schema)
        contract_columns = table_columns(db, "contracts")
        if "details" not in contract_columns:
            db.execute("ALTER TABLE contracts ADD COLUMN details TEXT NOT NULL DEFAULT ''")
        for column, definition in (
            ("service_date", "TEXT"),
            ("service_time", "TEXT"),
            ("service_address", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in contract_columns:
                db.execute(f"ALTER TABLE contracts ADD COLUMN {column} {definition}")
        db.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS contracts_one_active_per_provider_slot
               ON contracts(provider_id, service_date, service_time)
               WHERE service_date IS NOT NULL AND service_time IS NOT NULL
                 AND state IN ('Aguardando confirmação', 'Confirmado')"""
        )
        user_columns = table_columns(db, "users")
        for column in ("profile_bio", "profile_location", "profile_photo"):
            if column not in user_columns:
                db.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")


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
    is_registration = purpose == "register"
    action = "concluir seu cadastro" if is_registration else "desativar sua conta"
    subject = "Confirme seu cadastro no AutonoMe" if is_registration else "Confirme a desativação da sua conta AutonoMe"
    content = (
        f"Use este código para {action} no AutonoMe:\n\n"
        f"{code}\n\n"
        f"O código expira em 10 minutos. Se você não solicitou esta ação, ignore esta mensagem."
    )

    brevo_api_key = os.environ.get("BREVO_API_KEY")
    if brevo_api_key:
        sender = os.environ.get("EMAIL_FROM")
        if not sender:
            raise RuntimeError("Email delivery is not configured. Set EMAIL_FROM for BREVO_API_KEY.")
        payload = {
            "sender": {"name": os.environ.get("EMAIL_FROM_NAME", "AutonoMe"), "email": sender},
            "to": [{"email": address}],
            "subject": subject,
            "textContent": content,
        }
        request = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "accept": "application/json",
                "api-key": brevo_api_key,
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15):
            return

    host = os.environ.get("SMTP_HOST")
    sender = os.environ.get("SMTP_FROM")
    if not host or not sender:
        raise RuntimeError("Email delivery is not configured. Set BREVO_API_KEY and EMAIL_FROM, or SMTP_HOST and SMTP_FROM.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = address
    message.set_content(content)

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
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "profileBio": user["profile_bio"],
        "profileLocation": user["profile_location"],
        "profilePhoto": user["profile_photo"],
    }


def public_listing(row):
    return {
        "id": row["id"],
        "ownerId": row["user_id"],
        "name": row["name"],
        "service": row["service"],
        "category": row["category"],
        "initials": "".join(part[0] for part in row["name"].split()[:2]).upper(),
        "rating": "Novo",
        "location": row["location"],
        "about": row["about"],
        "price": row["price"],
        "isBooked": bool(row["is_booked"]),
        "profileBio": row["profile_bio"],
        "profileLocation": row["profile_location"],
        "profilePhoto": row["profile_photo"],
    }


def public_contract(row, current_user_id):
    is_client = row["client_id"] == current_user_id
    return {
        "id": row["id"],
        "listingId": row["listing_id"],
        "providerId": row["listing_id"] or row["provider_id"],
        "clientId": row["client_id"],
        "ownerId": row["provider_id"],
        "name": row["provider_name"] if is_client else row["client_name"],
        "service": row["service"],
        "date": row["date"],
        "details": row["details"],
        "serviceAddress": row["service_address"],
        "state": row["state"],
        "tab": "requested" if is_client else "hired",
        "category": row["category"],
        "location": row["location"],
        "price": row["price"],
        "about": row["about"],
        "clientName": row["client_name"],
        "providerName": row["provider_name"],
        "profilePhoto": row["provider_photo"] if is_client else row["client_photo"],
    }


def valid_service_time(value):
    return bool(re.fullmatch(r"(?:[01]\d|2[0-3]):(?:00|15|30|45)", value))


def parse_timezone_offset(value):
    if isinstance(value, bool) or not re.fullmatch(r"-?\d+", str(value)):
        raise APIError(HTTPStatus.BAD_REQUEST, "Fuso horário inválido.")
    try:
        offset = int(value)
    except (TypeError, ValueError) as error:
        raise APIError(HTTPStatus.BAD_REQUEST, "Fuso horário inválido.") from error
    if not -840 <= offset <= 840:
        raise APIError(HTTPStatus.BAD_REQUEST, "Fuso horário inválido.")
    return offset


def public_contract_note(row):
    return {
        "id": row["id"],
        "body": row["body"],
        "createdAt": row["created_at"],
    }


def public_notification(row):
    return {
        "id": row["id"],
        "contractId": row["contract_id"],
        "title": row["title"],
        "text": row["body"],
        "read": bool(row["is_read"]),
        "time": row["created_at"],
    }


def public_message(row, current_user_id):
    return {
        "id": row["id"],
        "contractId": row["contract_id"],
        "senderId": row["sender_id"],
        "senderName": row["sender_name"],
        "body": row["body"],
        "createdAt": row["created_at"],
        "mine": row["sender_id"] == current_user_id,
    }


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
        if length < 1 or length > MAX_JSON_BODY_BYTES:
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
        note_match = re.fullmatch(r"/api/contracts/([0-9a-f-]+)/notes", request_path)
        if request_path in {"/api/listings", "/api/contracts", "/api/messages", "/api/auth/profile", "/api/favorites", "/api/availability", "/api/notifications"} or note_match:
            try:
                if request_path == "/api/auth/profile":
                    with database() as db:
                        user = self.require_session_user(db)
                        response = {"user": public_user(user)}
                elif request_path == "/api/messages":
                    query = urlsplit(self.path).query
                    contract_id = parse_qs(query).get("contractId", [""])[0]
                    response = self.get_message_data(contract_id)
                elif request_path == "/api/availability":
                    query = parse_qs(urlsplit(self.path).query)
                    listing_id = query.get("listingId", [""])[0]
                    service_date = query.get("date", [""])[0]
                    offset = query.get("timezoneOffsetMinutes", ["0"])[0]
                    response = self.get_listing_availability(listing_id, service_date, offset) if listing_id else self.get_own_availability()
                elif request_path == "/api/notifications":
                    response = self.get_app_data(request_path)
                elif note_match:
                    response = self.get_contract_notes(note_match.group(1))
                else:
                    response = self.get_app_data(request_path)
                self.send_json(HTTPStatus.OK, response)
            except APIError as error:
                self.send_json(error.status, {"error": str(error)})
            except Exception:
                self.log_error("Unhandled API error:\n%s", traceback.format_exc())
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Não foi possível carregar os dados. Tente novamente."})
            return
        if request_path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint não encontrado."})
            return
        allowed_files = {
            "index.html", "style.css", "app.js", "manifest.webmanifest", "icon.svg", "logo_autonome.png",
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
            status, response, headers = self.handle_api(urlsplit(self.path).path, payload)
            self.send_json(status, response, headers)
        except APIError as error:
            self.send_json(error.status, {"error": str(error)})
        except Exception:
            self.log_error("Unhandled API error:\n%s", traceback.format_exc())
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Não foi possível concluir a solicitação. Tente novamente."})

    def do_DELETE(self):
        if not self.path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint não encontrado."})
            return
        try:
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                raise APIError(HTTPStatus.FORBIDDEN, "Origem da requisição não autorizada.")
            status, response, headers = self.handle_delete(urlsplit(self.path).path)
            self.send_json(status, response, headers)
        except APIError as error:
            self.send_json(error.status, {"error": str(error)})
        except Exception:
            self.log_error("Unhandled API error:\n%s", traceback.format_exc())
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Não foi possível concluir a solicitação. Tente novamente."})

    def handle_api(self, path, payload):
        if path == "/api/auth/profile":
            return self.update_profile(payload)
        if path == "/api/listings":
            return self.create_listing(payload)
        if path == "/api/messages":
            return self.create_message(payload)
        if path == "/api/contracts":
            return self.create_contract(payload)
        if path == "/api/availability":
            return self.save_availability(payload)
        if path == "/api/favorites":
            return self.add_favorite(payload)
        if path == "/api/notifications":
            return self.mark_all_notifications_read()
        match = re.fullmatch(r"/api/notifications/([0-9a-f-]+)/read", path)
        if match:
            return self.mark_notification_read(match.group(1))
        match = re.fullmatch(r"/api/contracts/([0-9a-f-]+)/notes", path)
        if match:
            return self.create_contract_note(match.group(1), payload)
        match = re.fullmatch(r"/api/listings/([0-9a-f-]+)", path)
        if match:
            return self.update_listing(match.group(1), payload)
        match = re.fullmatch(r"/api/contracts/([0-9a-f-]+)/status", path)
        if match:
            return self.update_contract_status(match.group(1), payload)
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

    def require_session_user(self, db):
        user = self.get_session_user(db)
        if user is None:
            raise APIError(HTTPStatus.UNAUTHORIZED, "Entre na sua conta para continuar.")
        return user

    def get_app_data(self, path):
        with database() as db:
            user = self.require_session_user(db)
            if path == "/api/listings":
                rows = db.execute(
                    """SELECT listings.*, users.name, users.profile_bio, users.profile_location, users.profile_photo,
                              EXISTS(
                                  SELECT 1 FROM contracts
                                  WHERE contracts.listing_id = listings.id
                                    AND contracts.state IN ('Aguardando confirmação', 'Confirmado')
                              ) AS is_booked
                       FROM listings JOIN users ON users.id = listings.user_id
                       WHERE listings.active = 1 ORDER BY listings.created_at DESC"""
                ).fetchall()
                return {"listings": [public_listing(row) for row in rows]}
            if path == "/api/favorites":
                rows = db.execute(
                    """SELECT listings.*, users.name, users.profile_bio, users.profile_location, users.profile_photo,
                              EXISTS(
                                  SELECT 1 FROM contracts
                                  WHERE contracts.listing_id = listings.id
                                    AND contracts.state IN ('Aguardando confirmação', 'Confirmado')
                              ) AS is_booked
                       FROM favorites
                       JOIN listings ON listings.id = favorites.listing_id AND listings.active = 1
                       JOIN users ON users.id = listings.user_id
                       WHERE favorites.user_id = ? ORDER BY favorites.created_at DESC""",
                    (user["id"],),
                ).fetchall()
                return {"favorites": [public_listing(row) for row in rows]}
            if path == "/api/notifications":
                rows = db.execute(
                    """SELECT id, contract_id, title, body, is_read, created_at
                       FROM notifications WHERE user_id = ? ORDER BY created_at DESC, rowid DESC""",
                    (user["id"],),
                ).fetchall()
                return {"notifications": [public_notification(row) for row in rows]}
            rows = db.execute(
                """SELECT contracts.*, listings.category, listings.location, listings.price, listings.about,
                          clients.name AS client_name, clients.profile_photo AS client_photo,
                          providers.name AS provider_name, providers.profile_photo AS provider_photo
                   FROM contracts
                   LEFT JOIN listings ON listings.id = contracts.listing_id
                   JOIN users AS clients ON clients.id = contracts.client_id
                   JOIN users AS providers ON providers.id = contracts.provider_id
                   WHERE contracts.client_id = ? OR contracts.provider_id = ?
                   ORDER BY contracts.created_at DESC""",
                (user["id"], user["id"]),
            ).fetchall()
            return {"contracts": [public_contract(row, user["id"]) for row in rows]}

    def get_own_availability(self):
        with database() as db:
            user = self.require_session_user(db)
            rows = db.execute(
                "SELECT weekday, service_time FROM availability WHERE user_id = ? ORDER BY weekday, service_time",
                (user["id"],),
            ).fetchall()
            return {"availability": [{"weekday": row["weekday"], "time": row["service_time"]} for row in rows]}

    def get_listing_availability(self, listing_id, service_date, timezone_offset_minutes=0):
        if not re.fullmatch(r"[0-9a-f-]{36}", listing_id):
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha um serviço válido.")
        offset = parse_timezone_offset(timezone_offset_minutes)
        try:
            selected_date = date.fromisoformat(service_date)
        except ValueError as error:
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha uma data válida.") from error
        if selected_date.isoformat() != service_date:
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha uma data válida.")
        with database() as db:
            self.require_session_user(db)
            listing = db.execute(
                "SELECT user_id FROM listings WHERE id = ? AND active = 1",
                (listing_id,),
            ).fetchone()
            if listing is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Este serviço não está mais disponível.")
            has_active_booking = db.execute(
                """SELECT 1 FROM contracts WHERE listing_id = ?
                   AND state IN ('Aguardando confirmação', 'Confirmado') LIMIT 1""",
                (listing_id,),
            ).fetchone()
            if has_active_booking:
                return {"configured": True, "times": []}
            has_schedule = db.execute(
                "SELECT 1 FROM availability WHERE user_id = ? LIMIT 1",
                (listing["user_id"],),
            ).fetchone()
            if not has_schedule:
                return {"configured": False, "times": []}
            rows = db.execute(
                """SELECT availability.service_time FROM availability
                   WHERE availability.user_id = ? AND availability.weekday = ?
                     AND NOT EXISTS (
                         SELECT 1 FROM contracts
                         WHERE contracts.provider_id = availability.user_id
                           AND contracts.service_date = ?
                           AND contracts.service_time = availability.service_time
                           AND contracts.state IN ('Aguardando confirmação', 'Confirmado')
                     )
                   ORDER BY availability.service_time""",
                (listing["user_id"], (selected_date.weekday() + 1) % 7, service_date),
            ).fetchall()
            local_now = datetime.now(timezone.utc) - timedelta(minutes=offset)
            times = [row["service_time"] for row in rows]
            if selected_date == local_now.date():
                times = [service_time for service_time in times if service_time > local_now.strftime("%H:%M")]
            return {"configured": True, "times": times}

    def save_availability(self, payload):
        slots = payload.get("availability")
        if not isinstance(slots, list) or len(slots) > 119:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe até 119 horários de atendimento.")
        validated = set()
        for slot in slots:
            if not isinstance(slot, dict):
                raise APIError(HTTPStatus.BAD_REQUEST, "Revise os horários informados.")
            weekday = slot.get("weekday")
            service_time = str(slot.get("time", ""))
            if isinstance(weekday, bool) or not isinstance(weekday, int) or not 0 <= weekday <= 6 or not valid_service_time(service_time):
                raise APIError(HTTPStatus.BAD_REQUEST, "Revise o dia e o horário informados.")
            validated.add((weekday, service_time))
        with database() as db:
            user = self.require_session_user(db)
            if user["role"] not in {"provider", "both"}:
                raise APIError(HTTPStatus.FORBIDDEN, "Ative o perfil profissional para configurar seus horários.")
            db.execute("DELETE FROM availability WHERE user_id = ?", (user["id"],))
            db.executemany(
                "INSERT INTO availability (user_id, weekday, service_time) VALUES (?, ?, ?)",
                [(user["id"], weekday, service_time) for weekday, service_time in sorted(validated)],
            )
        return HTTPStatus.OK, {"availability": [{"weekday": day, "time": value} for day, value in sorted(validated)]}, []

    def add_favorite(self, payload):
        listing_id = str(payload.get("listingId", ""))
        if not re.fullmatch(r"[0-9a-f-]{36}", listing_id):
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha um profissional válido.")
        with database() as db:
            user = self.require_session_user(db)
            listing = db.execute(
                "SELECT user_id FROM listings WHERE id = ? AND active = 1",
                (listing_id,),
            ).fetchone()
            if listing is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Este serviço não está mais disponível.")
            if listing["user_id"] == user["id"]:
                raise APIError(HTTPStatus.BAD_REQUEST, "Você não pode salvar seu próprio serviço.")
            db.execute(
                """INSERT INTO favorites (user_id, listing_id, created_at) VALUES (?, ?, ?)
                   ON CONFLICT (user_id, listing_id) DO NOTHING""",
                (user["id"], listing_id, int(time.time())),
            )
        return HTTPStatus.CREATED, {"message": "Profissional salvo nos favoritos."}, []

    def get_contract_notes(self, contract_id):
        with database() as db:
            user = self.require_session_user(db)
            contract = db.execute(
                "SELECT id FROM contracts WHERE id = ? AND (client_id = ? OR provider_id = ?)",
                (contract_id, user["id"], user["id"]),
            ).fetchone()
            if contract is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Contratação não encontrada.")
            rows = db.execute(
                """SELECT id, body, created_at FROM contract_notes
                   WHERE contract_id = ? AND user_id = ? ORDER BY created_at, rowid""",
                (contract_id, user["id"]),
            ).fetchall()
            return {"notes": [public_contract_note(row) for row in rows]}

    def create_contract_note(self, contract_id, payload):
        body = str(payload.get("body", "")).strip()
        if not body or len(body) > 2000:
            raise APIError(HTTPStatus.BAD_REQUEST, "A anotação deve ter entre 1 e 2.000 caracteres.")
        with database() as db:
            user = self.require_session_user(db)
            contract = db.execute(
                "SELECT id FROM contracts WHERE id = ? AND (client_id = ? OR provider_id = ?)",
                (contract_id, user["id"], user["id"]),
            ).fetchone()
            if contract is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Contratação não encontrada.")
            note_id = str(uuid.uuid4())
            created_at = int(time.time())
            db.execute(
                "INSERT INTO contract_notes (id, contract_id, user_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (note_id, contract_id, user["id"], body, created_at),
            )
        return HTTPStatus.CREATED, {"note": {"id": note_id, "body": body, "createdAt": created_at}}, []

    def mark_notification_read(self, notification_id):
        with database() as db:
            user = self.require_session_user(db)
            result = db.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                (notification_id, user["id"]),
            )
            if not result.rowcount:
                raise APIError(HTTPStatus.NOT_FOUND, "Notificação não encontrada.")
        return HTTPStatus.OK, {"message": "Notificação marcada como lida."}, []

    def mark_all_notifications_read(self):
        with database() as db:
            user = self.require_session_user(db)
            db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user["id"],))
        return HTTPStatus.OK, {"message": "Notificações marcadas como lidas."}, []

    @staticmethod
    def create_notification(db, user_id, contract_id, title, body, created_at):
        db.execute(
            """INSERT INTO notifications (id, user_id, contract_id, title, body, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), user_id, contract_id, title, body, created_at),
        )

    def get_message_data(self, contract_id):
        with database() as db:
            user = self.require_session_user(db)
            if not contract_id:
                rows = db.execute(
                    """SELECT contracts.id AS contract_id, contracts.service, contracts.date, contracts.state,
                              CASE WHEN contracts.client_id = ? THEN providers.name ELSE clients.name END AS other_name,
                              CASE WHEN contracts.client_id = ? THEN providers.profile_photo ELSE clients.profile_photo END AS other_photo,
                              (SELECT messages.body FROM messages WHERE messages.contract_id = contracts.id
                               ORDER BY messages.created_at DESC, messages.rowid DESC LIMIT 1) AS preview,
                              (SELECT messages.created_at FROM messages WHERE messages.contract_id = contracts.id
                               ORDER BY messages.created_at DESC, messages.rowid DESC LIMIT 1) AS last_message_at,
                              (SELECT COUNT(*) FROM messages WHERE messages.contract_id = contracts.id
                               AND messages.recipient_id = ? AND messages.read_at IS NULL) AS unread_count
                       FROM contracts
                       JOIN users AS clients ON clients.id = contracts.client_id
                       JOIN users AS providers ON providers.id = contracts.provider_id
                       WHERE (contracts.client_id = ? OR contracts.provider_id = ?)
                         AND contracts.state NOT IN ('Cancelada', 'Pedido negado')
                       ORDER BY COALESCE(last_message_at, contracts.updated_at) DESC""",
                    (user["id"], user["id"], user["id"], user["id"], user["id"]),
                ).fetchall()
                return {"conversations": [{
                    "contractId": row["contract_id"],
                    "service": row["service"],
                    "date": row["date"],
                    "state": row["state"],
                    "name": row["other_name"],
                    "profilePhoto": row["other_photo"],
                    "preview": row["preview"] or f"Conversa sobre {row['service']}",
                    "time": row["last_message_at"] or 0,
                    "unreadCount": row["unread_count"],
                } for row in rows]}

            contract = db.execute(
                """SELECT * FROM contracts WHERE id = ?
                   AND (client_id = ? OR provider_id = ?)
                   AND state NOT IN ('Cancelada', 'Pedido negado')""",
                (contract_id, user["id"], user["id"]),
            ).fetchone()
            if contract is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Conversa não encontrada ou indisponível.")
            db.execute(
                """UPDATE messages SET read_at = ?
                   WHERE contract_id = ? AND recipient_id = ? AND read_at IS NULL""",
                (int(time.time()), contract_id, user["id"]),
            )
            rows = db.execute(
                """SELECT messages.*, users.name AS sender_name
                   FROM messages JOIN users ON users.id = messages.sender_id
                   WHERE messages.contract_id = ?
                   ORDER BY messages.created_at, messages.rowid""",
                (contract_id,),
            ).fetchall()
            other_id = contract["provider_id"] if contract["client_id"] == user["id"] else contract["client_id"]
            other = db.execute("SELECT id, name, profile_photo FROM users WHERE id = ?", (other_id,)).fetchone()
            return {
                "conversation": {
                    "contractId": contract["id"],
                    "service": contract["service"],
                    "date": contract["date"],
                    "state": contract["state"],
                    "name": other["name"],
                    "profilePhoto": other["profile_photo"],
                },
                "messages": [public_message(row, user["id"]) for row in rows],
            }

    def create_message(self, payload):
        contract_id = str(payload.get("contractId", ""))
        body = str(payload.get("body", "")).strip()
        if not re.fullmatch(r"[0-9a-f-]{36}", contract_id):
            raise APIError(HTTPStatus.BAD_REQUEST, "Conversa inválida.")
        if not body or len(body) > 2_000:
            raise APIError(HTTPStatus.BAD_REQUEST, "A mensagem deve ter entre 1 e 2.000 caracteres.")
        with database() as db:
            user = self.require_session_user(db)
            contract = db.execute(
                """SELECT * FROM contracts WHERE id = ?
                   AND (client_id = ? OR provider_id = ?)
                   AND state NOT IN ('Cancelada', 'Pedido negado')""",
                (contract_id, user["id"], user["id"]),
            ).fetchone()
            if contract is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Conversa não encontrada ou indisponível.")
            recipient_id = contract["provider_id"] if contract["client_id"] == user["id"] else contract["client_id"]
            message_id = str(uuid.uuid4())
            created_at = int(time.time())
            db.execute(
                """INSERT INTO messages (id, contract_id, sender_id, recipient_id, body, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (message_id, contract_id, user["id"], recipient_id, body, created_at),
            )
            message = db.execute(
                """SELECT messages.*, users.name AS sender_name
                   FROM messages JOIN users ON users.id = messages.sender_id WHERE messages.id = ?""",
                (message_id,),
            ).fetchone()
        return HTTPStatus.CREATED, {"message": public_message(message, user["id"])}, []

    def create_listing(self, payload):
        category = str(payload.get("category", "")).strip()
        service = str(payload.get("service", "")).strip()
        location = str(payload.get("location", "")).strip()
        price = str(payload.get("price", "")).strip()
        about = str(payload.get("about", "")).strip()
        if not category or len(category) > 80:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe uma área de atuação válida.")
        if not service or len(service) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe o serviço oferecido.")
        if not location or len(location) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe sua cidade e estado.")
        if not price or len(price) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe o valor ou a forma de cobrança.")
        if not about or len(about) > 500:
            raise APIError(HTTPStatus.BAD_REQUEST, "A descrição deve ter até 500 caracteres.")
        with database() as db:
            user = self.require_session_user(db)
            if user["role"] == "client":
                db.execute("UPDATE users SET role = 'both' WHERE id = ?", (user["id"],))
            listing_id = str(uuid.uuid4())
            now = int(time.time())
            db.execute(
                """INSERT INTO listings (id, user_id, category, service, location, price, about, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (listing_id, user["id"], category, service, location, price, about, now),
            )
            updated_user = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            listing = db.execute(
                """SELECT listings.*, users.name, users.profile_bio, users.profile_location, users.profile_photo,
                          0 AS is_booked FROM listings
                   JOIN users ON users.id = listings.user_id WHERE listings.id = ?""",
                (listing_id,),
            ).fetchone()
        return HTTPStatus.CREATED, {"listing": public_listing(listing), "user": public_user(updated_user)}, []

    def update_listing(self, listing_id, payload):
        category = str(payload.get("category", "")).strip()
        service = str(payload.get("service", "")).strip()
        location = str(payload.get("location", "")).strip()
        price = str(payload.get("price", "")).strip()
        about = str(payload.get("about", "")).strip()
        if not category or len(category) > 80:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe uma área de atuação válida.")
        if not service or len(service) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe o serviço oferecido.")
        if not location or len(location) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe sua cidade e estado.")
        if not price or len(price) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe o valor ou a forma de cobrança.")
        if not about or len(about) > 500:
            raise APIError(HTTPStatus.BAD_REQUEST, "A descrição deve ter até 500 caracteres.")
        with database() as db:
            user = self.require_session_user(db)
            result = db.execute(
                """UPDATE listings SET category = ?, service = ?, location = ?, price = ?, about = ?
                   WHERE id = ? AND user_id = ? AND active = 1""",
                (category, service, location, price, about, listing_id, user["id"]),
            )
            if not result.rowcount:
                raise APIError(HTTPStatus.NOT_FOUND, "Anúncio não encontrado.")
            row = db.execute(
                """SELECT listings.*, users.name, users.profile_bio, users.profile_location,
                          users.profile_photo,
                          EXISTS(SELECT 1 FROM contracts WHERE contracts.listing_id = listings.id
                            AND contracts.state IN ('Aguardando confirmação', 'Confirmado')) AS is_booked
                   FROM listings JOIN users ON users.id = listings.user_id WHERE listings.id = ?""",
                (listing_id,),
            ).fetchone()
        return HTTPStatus.OK, {"listing": public_listing(row)}, []

    def update_profile(self, payload):
        name = str(payload.get("name", "")).strip()
        profile_bio = str(payload.get("profileBio", "")).strip()
        profile_location = str(payload.get("profileLocation", "")).strip()
        profile_photo = str(payload.get("profilePhoto", ""))
        if not name or len(name) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "Informe um nome com até 120 caracteres.")
        if len(profile_bio) > 500:
            raise APIError(HTTPStatus.BAD_REQUEST, "A apresentação deve ter até 500 caracteres.")
        if len(profile_location) > 120:
            raise APIError(HTTPStatus.BAD_REQUEST, "A localização deve ter até 120 caracteres.")
        if profile_photo:
            match = re.fullmatch(r"data:image/jpeg;base64,([A-Za-z0-9+/]*={0,2})", profile_photo)
            if not match:
                raise APIError(HTTPStatus.BAD_REQUEST, "A foto deve estar no formato JPEG.")
            try:
                photo_bytes = base64.b64decode(match.group(1), validate=True)
            except ValueError as error:
                raise APIError(HTTPStatus.BAD_REQUEST, "A foto enviada é inválida.") from error
            if len(photo_bytes) > MAX_PROFILE_PHOTO_BYTES or not photo_bytes.startswith(b"\xff\xd8") or not photo_bytes.endswith(b"\xff\xd9"):
                raise APIError(HTTPStatus.BAD_REQUEST, "A foto deve ter até 300 KB.")
        with database() as db:
            user = self.require_session_user(db)
            db.execute(
                """UPDATE users SET name = ?, profile_bio = ?, profile_location = ?,
                   profile_photo = ? WHERE id = ?""",
                (name, profile_bio, profile_location, profile_photo, user["id"]),
            )
            updated = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        return HTTPStatus.OK, {"user": public_user(updated)}, []

    def handle_delete(self, path):
        if path == "/api/notifications":
            with database() as db:
                user = self.require_session_user(db)
                db.execute("DELETE FROM notifications WHERE user_id = ?", (user["id"],))
            return HTTPStatus.OK, {"message": "Notificações removidas."}, []
        favorite_match = re.fullmatch(r"/api/favorites/([0-9a-f-]+)", path)
        if favorite_match:
            with database() as db:
                user = self.require_session_user(db)
                db.execute(
                    "DELETE FROM favorites WHERE user_id = ? AND listing_id = ?",
                    (user["id"], favorite_match.group(1)),
                )
            return HTTPStatus.OK, {"message": "Profissional removido dos favoritos."}, []
        match = re.fullmatch(r"/api/listings/([0-9a-f-]+)", path)
        if not match:
            raise APIError(HTTPStatus.NOT_FOUND, "Endpoint não encontrado.")
        with database() as db:
            user = self.require_session_user(db)
            listing = db.execute("SELECT id, user_id FROM listings WHERE id = ?", (match.group(1),)).fetchone()
            if listing is None or listing["user_id"] != user["id"]:
                raise APIError(HTTPStatus.NOT_FOUND, "Anúncio não encontrado.")
            db.execute("UPDATE listings SET active = 0 WHERE id = ?", (listing["id"],))
        return HTTPStatus.OK, {"message": "Anúncio removido."}, []

    def create_contract(self, payload):
        listing_id = str(payload.get("listingId", ""))
        service_date = str(payload.get("serviceDate", "")).strip()
        service_time = str(payload.get("time", "")).strip()
        service_address = str(payload.get("address", "")).strip()
        details = str(payload.get("details", "")).strip()
        offset = parse_timezone_offset(payload.get("timezoneOffsetMinutes", 0))
        if not re.fullmatch(r"[0-9a-f-]{36}", listing_id):
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha um serviço válido.")
        try:
            selected_date = date.fromisoformat(service_date)
        except ValueError as error:
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha uma data válida.") from error
        local_now = datetime.now(timezone.utc) - timedelta(minutes=offset)
        if selected_date.isoformat() != service_date or selected_date < local_now.date():
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha uma data futura.")
        if not valid_service_time(service_time):
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha um horário válido.")
        if selected_date == local_now.date() and service_time <= local_now.strftime("%H:%M"):
            raise APIError(HTTPStatus.BAD_REQUEST, "Escolha um horário futuro.")
        if len(details) > 500:
            raise APIError(HTTPStatus.BAD_REQUEST, "Os detalhes do pedido devem ter até 500 caracteres.")
        if len(service_address) > 250:
            raise APIError(HTTPStatus.BAD_REQUEST, "O endereço deve ter até 250 caracteres.")
        with database() as db:
            client = self.require_session_user(db)
            if client["role"] == "provider":
                raise APIError(HTTPStatus.FORBIDDEN, "Ative também o perfil de contratante para solicitar um serviço.")
            listing = db.execute(
                """SELECT listings.*, users.name AS provider_name, users.role AS provider_role
                   FROM listings JOIN users ON users.id = listings.user_id
                   WHERE listings.id = ? AND listings.active = 1""",
                (listing_id,),
            ).fetchone()
            if listing is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Este serviço não está mais disponível.")
            if listing["user_id"] == client["id"]:
                raise APIError(HTTPStatus.FORBIDDEN, "Você não pode contratar o seu próprio serviço.")
            has_schedule = db.execute(
                "SELECT 1 FROM availability WHERE user_id = ? LIMIT 1",
                (listing["user_id"],),
            ).fetchone()
            if not has_schedule:
                raise APIError(HTTPStatus.CONFLICT, "Este profissional ainda não configurou os horários de atendimento.")
            available_slot = db.execute(
                """SELECT 1 FROM availability WHERE user_id = ? AND weekday = ? AND service_time = ?""",
                (listing["user_id"], (selected_date.weekday() + 1) % 7, service_time),
            ).fetchone()
            if not available_slot:
                raise APIError(HTTPStatus.CONFLICT, "O profissional não disponibilizou esse horário.")
            occupied_slot = db.execute(
                """SELECT 1 FROM contracts WHERE provider_id = ? AND service_date = ? AND service_time = ?
                   AND state IN ('Aguardando confirmação', 'Confirmado') LIMIT 1""",
                (listing["user_id"], service_date, service_time),
            ).fetchone()
            if occupied_slot:
                raise APIError(HTTPStatus.CONFLICT, "Este horário acabou de ser reservado. Escolha outro.")
            weekday_names = ("Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb")
            date_label = f"{weekday_names[(selected_date.weekday() + 1) % 7]}, {selected_date:%d/%m/%Y} às {service_time}"
            try:
                contract_id = str(uuid.uuid4())
                now = int(time.time())
                db.execute(
                    """INSERT INTO contracts
                       (id, listing_id, client_id, provider_id, service, date, details, service_date, service_time,
                        service_address, state, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Aguardando confirmação', ?, ?)""",
                    (contract_id, listing_id, client["id"], listing["user_id"], listing["service"], date_label,
                     details, service_date, service_time, service_address, now, now),
                )
                self.create_notification(
                    db,
                    listing["user_id"],
                    contract_id,
                    "Novo pedido de contratação",
                    f"{client['name']} solicitou {listing['service']} para {date_label}.",
                    now,
                )
            except DATABASE_INTEGRITY_ERRORS as error:
                constraint_name = getattr(getattr(error, "diag", None), "constraint_name", "")
                if "contracts_one_active_per_listing" in constraint_name or "contracts.listing_id" in str(error):
                    raise APIError(HTTPStatus.CONFLICT, "Este profissional já recebeu um pedido ativo para este serviço.") from error
                if "contracts_one_active_per_provider_slot" in constraint_name or "contracts.provider_id" in str(error):
                    raise APIError(HTTPStatus.CONFLICT, "Este horário acabou de ser reservado. Escolha outro.") from error
                raise
            row = db.execute(
                """SELECT contracts.*, listings.category, listings.location, listings.price, listings.about,
                       clients.name AS client_name, clients.profile_photo AS client_photo,
                       providers.name AS provider_name, providers.profile_photo AS provider_photo
                   FROM contracts JOIN listings ON listings.id = contracts.listing_id
                   JOIN users AS clients ON clients.id = contracts.client_id
                   JOIN users AS providers ON providers.id = contracts.provider_id
                   WHERE contracts.id = ?""",
                (contract_id,),
            ).fetchone()
        return HTTPStatus.CREATED, {"contract": public_contract(row, client["id"])}, []

    def update_contract_status(self, contract_id, payload):
        status = str(payload.get("status", ""))
        if status not in {"confirm", "decline", "cancel"}:
            raise APIError(HTTPStatus.BAD_REQUEST, "Ação de contratação inválida.")
        with database() as db:
            user = self.require_session_user(db)
            contract = db.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,)).fetchone()
            if contract is None:
                raise APIError(HTTPStatus.NOT_FOUND, "Contratação não encontrada.")
            if status in {"confirm", "decline"}:
                if contract["provider_id"] != user["id"] or contract["state"] != "Aguardando confirmação":
                    raise APIError(HTTPStatus.FORBIDDEN, "Você não pode responder a esta contratação.")
                new_state = "Confirmado" if status == "confirm" else "Pedido negado"
            else:
                if contract["client_id"] != user["id"] or contract["state"] not in {"Aguardando confirmação", "Confirmado"}:
                    raise APIError(HTTPStatus.FORBIDDEN, "Você não pode cancelar esta contratação.")
                new_state = "Cancelada"
            db.execute(
                "UPDATE contracts SET state = ?, updated_at = ? WHERE id = ?",
                (new_state, int(time.time()), contract_id),
            )
            recipient_id = contract["client_id"] if status in {"confirm", "decline"} else contract["provider_id"]
            notification_title = {
                "confirm": "Pedido confirmado",
                "decline": "Pedido recusado",
                "cancel": "Contratação cancelada",
            }[status]
            notification_body = {
                "confirm": f"Seu pedido de {contract['service']} foi confirmado.",
                "decline": f"Seu pedido de {contract['service']} foi recusado.",
                "cancel": f"O pedido de {contract['service']} foi cancelado.",
            }[status]
            self.create_notification(db, recipient_id, contract_id, notification_title, notification_body, int(time.time()))
            row = db.execute(
                """SELECT contracts.*, listings.category, listings.location, listings.price, listings.about,
                          clients.name AS client_name, clients.profile_photo AS client_photo,
                          providers.name AS provider_name, providers.profile_photo AS provider_photo
                   FROM contracts LEFT JOIN listings ON listings.id = contracts.listing_id
                   JOIN users AS clients ON clients.id = contracts.client_id
                   JOIN users AS providers ON providers.id = contracts.provider_id
                   WHERE contracts.id = ?""",
                (contract_id,),
            ).fetchone()
        return HTTPStatus.OK, {"contract": public_contract(row, user["id"])}, []

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
                raise APIError(HTTPStatus.SERVICE_UNAVAILABLE, SMTP_NOT_CONFIGURED_MESSAGE) from error
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
                raise APIError(HTTPStatus.SERVICE_UNAVAILABLE, SMTP_NOT_CONFIGURED_MESSAGE) from error
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
                raise APIError(HTTPStatus.SERVICE_UNAVAILABLE, SMTP_NOT_CONFIGURED_MESSAGE) from error
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
