"""Autenticação de utilizadores.

Dois modos, controlados por ``AUTH_MODE``:

* ``local`` (desenvolvimento) — valida a palavra-passe pelo hash guardado no User.
* ``ldap``  (produção)        — valida a "palavra-passe do computador" fazendo
                                 bind no Active Directory do domínio.

Em ambos os casos o utilizador tem de existir na tabela ``users`` e estar
activo; o Active Directory apenas confirma a identidade/palavra-passe, não cria
contas nem atribui perfis.
"""

import os

from flask import current_app

from app.models.user import User
from app.repositories.users import UserRepository


def normalizar_username(valor):
    return (valor or "").strip().upper()


def _mongo_users_ativo() -> bool:
    return os.environ.get("USE_MONGO_USERS", "0").strip().lower() in {"1", "true", "yes", "on"}


def autenticar(username, password):
    """Devolve o utilizador autenticado em SQLite ou Mongo conforme a flag de migração."""
    username = normalizar_username(username)
    if not username or not password:
        return None

    if _mongo_users_ativo():
        repo = UserRepository()
        utilizador = repo.get_by_username(username)
        if utilizador is None or not utilizador.ativo:
            return None
        modo = (current_app.config.get("AUTH_MODE") or "local").lower()
        if modo == "ldap":
            return utilizador if _validar_ldap(username, password) else None
        return utilizador if utilizador.verificar_password(password) else None

    utilizador = User.query.filter_by(username=username).first()
    if utilizador is None or not utilizador.ativo:
        return None

    modo = (current_app.config.get("AUTH_MODE") or "local").lower()
    if modo == "ldap":
        return utilizador if _validar_ldap(username, password) else None

    return utilizador if utilizador.verificar_password(password) else None


def _validar_ldap(username, password):
    """Tenta autenticar ``username``/``password`` contra o Active Directory."""
    try:
        from ldap3 import ALL, NTLM, Connection, Server
        from ldap3.core.exceptions import LDAPException
    except ImportError:  # pragma: no cover
        current_app.logger.error("AUTH_MODE=ldap mas o pacote 'ldap3' não está instalado.")
        return False

    host = current_app.config.get("LDAP_HOST")
    dominio = current_app.config.get("LDAP_DOMAIN")
    if not host or not dominio:
        current_app.logger.error("LDAP_HOST / LDAP_DOMAIN não configurados.")
        return False

    servidor = Server(
        host,
        port=current_app.config.get("LDAP_PORT", 636),
        use_ssl=current_app.config.get("LDAP_USE_SSL", True),
        get_info=ALL,
        connect_timeout=8,
    )
    conta = f"{dominio}\\{username}"
    try:
        conexao = Connection(
            servidor,
            user=conta,
            password=password,
            authentication=NTLM,
            auto_bind=True,
            receive_timeout=8,
        )
        conexao.unbind()
        return True
    except LDAPException as exc:
        current_app.logger.info("Autenticação LDAP falhou para %s: %s", username, exc)
        return False
    except Exception:  # pragma: no cover - rede/SSL inesperado
        current_app.logger.exception("Erro inesperado ao contactar o Active Directory.")
        return False
