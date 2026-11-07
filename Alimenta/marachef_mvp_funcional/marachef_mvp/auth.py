import hashlib
import hmac
import json
import os
import secrets
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

COOKIE = "marachef"
SESSION_TTL = 8 * 60 * 60
ROLES = {"administrador", "chef", "funcionario"}
REVIEWERS = {"administrador", "chef"}


@dataclass(frozen=True)
class User:
    name: str
    role: str


def users_file():
    filename = os.getenv("MARACHEF_USERS_FILE")
    return Path(filename) if filename else None


def users():
    path = users_file()
    try:
        if path:
            raw = path.read_text(encoding="utf-8") if path.exists() else "{}"
        else:
            raw = os.getenv("MARACHEF_USERS", "{}")
        accounts = json.loads(raw)
        if not isinstance(accounts, dict) or any(
            not isinstance(value, dict) or value.get("role") not in ROLES
            or not isinstance(value.get("hash"), str) for value in accounts.values()
        ):
            raise ValueError
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "A configuração de contas do servidor está indisponível.") from exc
    return accounts


def save_users(path, accounts):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(accounts, file)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def derive(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def password_hash(password):
    salt = secrets.token_bytes(16)
    return salt.hex() + "$" + derive(password, salt)


def login(name, password):
    account = users().get(name)
    encoded = account["hash"] if account else ""
    try:
        salt, expected = encoded.split("$", 1)
        salt = bytes.fromhex(salt)
        if len(salt) != 16 or len(expected) != 128:
            raise ValueError
    except ValueError:
        salt, expected = b"\0" * 16, ""
    if not hmac.compare_digest(derive(password, salt), expected):
        raise HTTPException(401, "Usuário ou senha inválidos.")
    return User(name, account["role"])


def signer():
    secret = os.getenv("MARACHEF_SESSION_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(503, "Configure MARACHEF_SESSION_SECRET no servidor.")
    return URLSafeTimedSerializer(secret, salt="marachef-auth")


def fingerprint(account):
    return hashlib.sha256(account["hash"].encode()).hexdigest()


def session_token(user):
    return signer().dumps([user.name, fingerprint(users()[user.name])])


def current_user(request: Request):
    token = request.cookies.get(COOKIE)
    if token:
        try:
            name, version = signer().loads(token, max_age=SESSION_TTL)
            account = users().get(name)
            if account and hmac.compare_digest(fingerprint(account), version):
                return User(name, account["role"])
        except BadSignature:
            pass
    raise HTTPException(401, "Entre para continuar.")


def require(user, roles):
    if user.role not in roles:
        raise HTTPException(403, "Seu perfil não pode executar esta ação.")
