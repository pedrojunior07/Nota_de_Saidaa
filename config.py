"""
Configurações da aplicação Nota de Saída.

A URI da base de dados pode ser substituída pela variável de ambiente
DATABASE_URL, permitindo a migração futura para PostgreSQL sem alterar código.
"""

import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _sqlite_uri():
    """Constrói uma URI SQLite compatível com Windows e Unix."""
    db_path = os.path.join(basedir, "instance", "nota_saida.db")
    return "sqlite:///" + db_path.replace("\\", "/")


class Config:
    """Configuração base (desenvolvimento e produção)."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-nota-saida-altere-em-producao")

    # SQLite por omissão; em produção defina DATABASE_URL (postgresql://...)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _sqlite_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    ITEMS_PER_PAGE = 10
    PDF_FOLDER = os.path.join(basedir, "instance", "pdfs")
    SIGNATURE_FOLDER = os.path.join(basedir, "instance", "signatures")

    APP_NAME = "Nota de Saída"
    APP_SHORT_NAME = "NDS"

    # ------------------------------------------------------------------
    # Autenticação
    #   AUTH_MODE = "local"  -> valida a palavra-passe pelo hash local (dev)
    #   AUTH_MODE = "ldap"   -> valida no Active Directory (palavra-passe do PC)
    # ------------------------------------------------------------------
    AUTH_MODE = os.environ.get("AUTH_MODE", "local")

    LDAP_HOST = os.environ.get("LDAP_HOST", "")          # opcional: força um servidor; vazio = descoberta automática via DNS
    LDAP_PORT = int(os.environ.get("LDAP_PORT", "636"))
    LDAP_USE_SSL = os.environ.get("LDAP_USE_SSL", "1") != "0"
    # Domínio real (confirmado a partir da biblioteca interna do banco
    # "jactive-directory"): mz.sbicdirectory.com. Não é NetBIOS — é o
    # domínio de DNS, usado para montar o "principal" de bind no formato
    # "utilizador@dominio" (ver app/utils/active_directory.py).
    LDAP_DOMAIN = os.environ.get("LDAP_DOMAIN", "mz.sbicdirectory.com")
    # Opcional: se ficar vazio, é derivada automaticamente de LDAP_DOMAIN
    # (mz.sbicdirectory.com -> DC=mz,DC=sbicdirectory,DC=com).
    LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "")

    # ------------------------------------------------------------------
    # Pesquisa de destinatários no diretório (campo "Para" da Nota de Saída)
    #   DIRECTORY_MODE = "simulacao" -> lista local de exemplo (sem AD)
    #   DIRECTORY_MODE = "ldap"      -> pesquisa no Active Directory
    # A pesquisa LDAP usa uma CONTA DE SERVIÇO (não as credenciais do
    # utilizador): defina LDAP_BIND_DN e LDAP_BIND_PASSWORD.
    # ------------------------------------------------------------------
    DIRECTORY_MODE = os.environ.get("DIRECTORY_MODE", "simulacao")
    LDAP_BIND_DN = os.environ.get("LDAP_BIND_DN", "")          # ex.: CN=svc-nota-saida,OU=Serviços,DC=standardbank,DC=co,DC=mz
    LDAP_BIND_PASSWORD = os.environ.get("LDAP_BIND_PASSWORD", "")
    LDAP_DIRECTORY_FILTER = os.environ.get("LDAP_DIRECTORY_FILTER", "")  # opcional; use {q} para o termo

    # Formato aceite para o nome de utilizador (nº de colaborador), ex.: A272754
    USERNAME_REGEX = os.environ.get("USERNAME_REGEX", r"^[A-Za-z]{1,2}\d{4,8}$")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    AUTH_MODE = os.environ.get("AUTH_MODE", "ldap")


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
