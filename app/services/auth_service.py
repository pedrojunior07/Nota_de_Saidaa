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
    """Tenta autenticar ``username``/``password`` contra o Active Directory.

    Bind SIMPLE com o "principal" no formato "utilizador@domínio"
    (userPrincipalName) — confirmado a partir da biblioteca interna do
    banco jactive-directory (ver app/utils/active_directory.py). Não usa
    NTLM nem o formato "DOMÍNIO\\utilizador".

    Não depende de um LDAP_HOST fixo: por omissão descobre os
    controladores de domínio reais via DNS (SRV) e tenta cada um por
    ordem, até um autenticar com sucesso — LDAP_HOST só força um servidor
    específico, se definido.
    """
    try:
        from ldap3 import ALL, SIMPLE, Connection, Server
        from ldap3.core.exceptions import LDAPException
    except ImportError:  # pragma: no cover
        current_app.logger.error("AUTH_MODE=ldap mas o pacote 'ldap3' não está instalado.")
        return False

    from app.utils.active_directory import DOMINIO_OMISSAO, montar_principal, obter_candidatos_ldap

    dominio = current_app.config.get("LDAP_DOMAIN") or DOMINIO_OMISSAO
    candidatos = obter_candidatos_ldap(dominio, current_app.config.get("LDAP_HOST"))
    principal = montar_principal(username, dominio)
    porta_omissao = current_app.config.get("LDAP_PORT", 636)
    usar_ssl = current_app.config.get("LDAP_USE_SSL", True)

    ultimo_erro = None
    for host, porta_descoberta in candidatos:
        servidor = Server(
            host,
            port=porta_descoberta or porta_omissao,
            use_ssl=usar_ssl,
            get_info=ALL,
            connect_timeout=8,
        )
        try:
            conexao = Connection(
                servidor,
                user=principal,
                password=password,
                authentication=SIMPLE,
                auto_bind=True,
                receive_timeout=8,
            )
            conexao.unbind()
            return True
        except LDAPException as exc:
            ultimo_erro = exc
            current_app.logger.info(
                "Autenticação LDAP falhou em %s:%s para %s: %s", host, porta_descoberta or porta_omissao, username, exc
            )
        except Exception as exc:  # pragma: no cover - rede/SSL inesperado
            ultimo_erro = exc
            current_app.logger.exception("Erro inesperado ao contactar %s.", host)

    if ultimo_erro is None:
        current_app.logger.error(
            "Autenticação LDAP: não foi possível descobrir nenhum controlador de domínio para %s.", dominio
        )
    return False
