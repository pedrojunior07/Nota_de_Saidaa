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

    # Exigir uma signature pad ligada (detetada por WebHID) para recolher a
    # assinatura do destinatário/segurança. Em desenvolvimento fica desligado
    # para permitir assinar com rato/touch sem hardware.
    SIGNATURE_PAD_REQUIRED = os.environ.get("SIGNATURE_PAD_REQUIRED", "0") == "1"

    # ------------------------------------------------------------------
    # Signature pad Wacom STU (via serviço local "STU-SigCaptX", instalado
    # no PC onde se recolhe a assinatura). O browser liga-se por HTTPS a
    # localhost:<porta> — ver app/static/js/wacom_sigpad.js e o guia em
    # docs/WACOM_STU_SETUP.md para o passo a passo completo de instalação.
    #
    #   WACOM_SIGCAPTX_PORT    -> porta do serviço STU-SigCaptX. A Wacom usa
    #                             9000 por omissão (registo do Windows,
    #                             chave ServicePort) — só mude se o
    #                             instalador ficou configurado com outra.
    #   WACOM_SIGCAPTX_LICENCE -> chave de licença. A Wacom disponibiliza
    #                             uma licença "Lite" gratuita, válida para
    #                             desenvolvimento e produção (só não cobre
    #                             encriptação de assinatura nem formatação
    #                             ISO — nada disto é usado aqui), por isso
    #                             já vem pré-configurada como valor por
    #                             omissão. Pode substituir por uma licença
    #                             paga própria via variável de ambiente.
    #
    # Sem o serviço instalado (ou sem o pad ligado) a app continua a
    # funcionar normalmente: assina-se no <canvas> com rato/touch/caneta.
    # ------------------------------------------------------------------
    WACOM_SIGCAPTX_PORT = int(os.environ.get("WACOM_SIGCAPTX_PORT", "9000"))
    WACOM_SIGCAPTX_LICENCE_LITE = (
        "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiI3YmM5Y2IxYWIxMGE0NmUxODI2N2E5MTJkYTA2ZTI3NiIsImV4cCI6MjE0NzQ4MzY0NywiaWF0IjoxNTYwOTUwMjcyLCJyaWdodHMiOlsiU0lHX1NES19DT1JFIiwiU0lHQ0FQVFhfQUNDRVNTIl0sImRldmljZXMiOlsiV0FDT01fQU5ZIl0sInR5cGUiOiJwcm9kIiwibGljX25hbWUiOiJTaWduYXR1cmUgU0RLIiwid2Fjb21faWQiOiI3YmM5Y2IxYWIxMGE0NmUxODI2N2E5MTJkYTA2ZTI3NiIsImxpY191aWQiOiJiODUyM2ViYi0xOGI3LTQ3OGEtYTlkZS04NDlmZTIyNmIwMDIiLCJhcHBzX3dpbmRvd3MiOltdLCJhcHBzX2lvcyI6W10sImFwcHNfYW5kcm9pZCI6W10sIm1hY2hpbmVfaWRzIjpbXX0.ONy3iYQ7lC6rQhou7rz4iJT_OJ20087gWz7GtCgYX3uNtKjmnEaNuP3QkjgxOK_vgOrTdwzD-nm-ysiTDs2GcPlOdUPErSp_bcX8kFBZVmGLyJtmeInAW6HuSp2-57ngoGFivTH_l1kkQ1KMvzDKHJbRglsPpd4nVHhx9WkvqczXyogldygvl0LRidyPOsS5H2GYmaPiyIp9In6meqeNQ1n9zkxSHo7B11mp_WXJXl0k1pek7py8XYCedCNW5qnLi4UCNlfTd6Mk9qz31arsiWsesPeR9PN121LBJtiPi023yQU8mgb9piw_a-ccciviJuNsEuRDN3sGnqONG3dMSA"
    )
    WACOM_SIGCAPTX_LICENCE = os.environ.get("WACOM_SIGCAPTX_LICENCE") or WACOM_SIGCAPTX_LICENCE_LITE

    APP_NAME = "Nota de Saída"
    APP_SHORT_NAME = "NDS"

    # ------------------------------------------------------------------
    # Autenticação
    #   AUTH_MODE = "local"  -> valida a palavra-passe pelo hash local (dev)
    #   AUTH_MODE = "ldap"   -> valida no Active Directory (palavra-passe do PC)
    # ------------------------------------------------------------------
    AUTH_MODE = os.environ.get("AUTH_MODE", "local")

    LDAP_HOST = os.environ.get("LDAP_HOST", "")          # ex.: dc01.standardbank.co.mz
    LDAP_PORT = int(os.environ.get("LDAP_PORT", "636"))
    LDAP_USE_SSL = os.environ.get("LDAP_USE_SSL", "1") != "0"
    LDAP_DOMAIN = os.environ.get("LDAP_DOMAIN", "")      # domínio NetBIOS, ex.: SBM
    LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "")    # ex.: DC=standardbank,DC=co,DC=mz

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
    SIGNATURE_PAD_REQUIRED = os.environ.get("SIGNATURE_PAD_REQUIRED", "1") == "1"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
