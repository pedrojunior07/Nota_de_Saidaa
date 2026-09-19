"""Pesquisa de pessoas no diretório da instituição (Active Directory).

Dois modos, controlados por ``DIRECTORY_MODE``:

* ``simulacao`` (predefinido) — resultados de uma lista local de exemplo. Serve
  para desenvolver e testar o formulário da Nota de Saída enquanto ainda não há
  acesso ao endpoint / Active Directory do banco.
* ``ldap`` — pesquisa real no Active Directory por e-mail, nome ou nº de
  colaborador, usando uma conta de serviço (``LDAP_BIND_DN`` /
  ``LDAP_BIND_PASSWORD``).

Para trocar quando o acesso estiver disponível basta pôr ``DIRECTORY_MODE=ldap``
no ``.env`` e preencher as credenciais. A interface pública — :func:`procurar_pessoas`
— não muda, por isso o formulário e o JavaScript continuam iguais.

Formato de cada resultado (dict)::

    {
        "email": "nome.apelido@standardbank.co.mz",
        "nome": "Nome Apelido",
        "departamento": "Recursos Humanos",
        "cargo": "Analista",          # opcional
        "username": "A123456",        # opcional (nº de colaborador)
        "origem": "simulacao" | "ldap",
    }
"""

from __future__ import annotations

import unicodedata

from flask import current_app

TERMO_MINIMO = 2

# ---------------------------------------------------------------------------
# Lista de simulação — colaboradores fictícios do banco.
# Substituída pela pesquisa LDAP quando DIRECTORY_MODE=ldap.
# ---------------------------------------------------------------------------
_PESSOAS_SIMULADAS: list[dict] = [
    {"email": "clementina.elihud@standardbank.co.mz", "nome": "Clementina Elihud", "departamento": "Informática", "cargo": "Programadora", "username": "A310457"},
    {"email": "maria.silva@standardbank.co.mz", "nome": "Maria Silva", "departamento": "Recursos Humanos", "cargo": "Técnica de Recrutamento", "username": "A301145"},
    {"email": "joao.cossa@standardbank.co.mz", "nome": "João Cossa", "departamento": "Operações", "cargo": "Analista de Operações", "username": "A288390"},
    {"email": "paula.nhantumbo@standardbank.co.mz", "nome": "Paula Nhantumbo", "departamento": "Crédito", "cargo": "Gestora de Crédito", "username": "A275501"},
    {"email": "sergio.langa@standardbank.co.mz", "nome": "Sérgio Langa", "departamento": "Tesouraria", "cargo": "Dealer", "username": "A266740"},
    {"email": "ana.macamo@standardbank.co.mz", "nome": "Ana Macamo", "departamento": "Auditoria Interna", "cargo": "Auditora Sénior", "username": "A200550"},
    {"email": "carlos.mendes@standardbank.co.mz", "nome": "Carlos Mendes", "departamento": "Informática", "cargo": "Técnico de Informática", "username": "A272754"},
    {"email": "beatriz.chissano@standardbank.co.mz", "nome": "Beatriz Chissano", "departamento": "Compliance", "cargo": "Oficial de Compliance", "username": "A311902"},
    {"email": "nelson.come@standardbank.co.mz", "nome": "Nelson Come", "departamento": "Banca de Empresas", "cargo": "Gestor de Relação", "username": "A249317"},
    {"email": "sandra.machava@standardbank.co.mz", "nome": "Sandra Machava", "departamento": "Marketing", "cargo": "Coordenadora de Marca", "username": "A293648"},
    {"email": "tomas.uamusse@standardbank.co.mz", "nome": "Tomás Uamusse", "departamento": "Gestão de Risco", "cargo": "Analista de Risco de Mercado", "username": "A281455"},
    {"email": "filipa.dava@standardbank.co.mz", "nome": "Filipa Dava", "departamento": "Jurídico", "cargo": "Jurista", "username": "A305218"},
    {"email": "rui.tembe@standardbank.co.mz", "nome": "Rui Tembe", "departamento": "Rede de Balcões", "cargo": "Gerente de Balcão", "username": "A230984"},
    {"email": "olivia.mondlane@standardbank.co.mz", "nome": "Olívia Mondlane", "departamento": "Recuperação de Crédito", "cargo": "Técnica de Recuperação", "username": "A298773"},
    {"email": "helder.sitoe@standardbank.co.mz", "nome": "Hélder Sitoe", "departamento": "Contabilidade", "cargo": "Contabilista", "username": "A254001"},
    {"email": "isabel.guambe@standardbank.co.mz", "nome": "Isabel Guambe", "departamento": "Recursos Humanos", "cargo": "Business Partner de RH", "username": "A312560"},
    {"email": "dinis.matola@standardbank.co.mz", "nome": "Dinis Matola", "departamento": "Informática", "cargo": "Administrador de Sistemas", "username": "A241188"},
    {"email": "gina.bila@standardbank.co.mz", "nome": "Gina Bila", "departamento": "Tesouraria", "cargo": "Back Office de Mercados", "username": "A307419"},
    {"email": "armando.zavala@standardbank.co.mz", "nome": "Armando Zavala", "departamento": "Segurança", "cargo": "Coordenador de Segurança Física", "username": "A222075"},
    {"email": "lucia.fumo@standardbank.co.mz", "nome": "Lúcia Fumo", "departamento": "Operações", "cargo": "Supervisora de Compensação", "username": "A290012"},
    {"email": "edson.mucavele@standardbank.co.mz", "nome": "Édson Mucavele", "departamento": "Banca de Retalho", "cargo": "Gestor de Produto", "username": "A283901"},
    {"email": "jose.matsinhe@standardbank.co.mz", "nome": "José Matsinhe", "departamento": "Informática", "cargo": "Técnico de Suporte", "username": "A247712"},
    {"email": "celia.novela@standardbank.co.mz", "nome": "Célia Novela", "departamento": "Compliance", "cargo": "Analista de KYC", "username": "A309883"},
    {"email": "abel.chiziane@standardbank.co.mz", "nome": "Abel Chiziane", "departamento": "Crédito", "cargo": "Analista de Crédito", "username": "A268104"},
    {"email": "vania.sitole@standardbank.co.mz", "nome": "Vânia Sitole", "departamento": "Marketing", "cargo": "Gestora de Campanhas", "username": "A314026"},
]


def _sem_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn").lower()


def procurar_pessoas(termo: str, limite: int = 10) -> list[dict]:
    """Devolve até ``limite`` pessoas cujo e-mail, nome ou departamento casa com ``termo``."""
    termo = (termo or "").strip()
    if len(termo) < TERMO_MINIMO:
        return []

    modo = (current_app.config.get("DIRECTORY_MODE") or "simulacao").lower()
    if modo == "ldap":
        return _procurar_ldap(termo, limite)
    return _procurar_simulacao(termo, limite)


# ---------------------------------------------------------------------------
# Modo simulação
# ---------------------------------------------------------------------------
def _procurar_simulacao(termo: str, limite: int) -> list[dict]:
    alvo = _sem_acentos(termo)
    encontrados = [
        pessoa
        for pessoa in _PESSOAS_SIMULADAS
        if alvo in _sem_acentos(pessoa["email"])
        or alvo in _sem_acentos(pessoa["nome"])
        or alvo in _sem_acentos(pessoa["departamento"])
        or alvo in _sem_acentos(pessoa.get("username", ""))
    ]
    # e-mails que começam pelo termo aparecem primeiro; depois por nome
    encontrados.sort(
        key=lambda p: (not _sem_acentos(p["email"]).startswith(alvo), p["nome"])
    )
    return [dict(p, origem="simulacao") for p in encontrados[:limite]]


# ---------------------------------------------------------------------------
# Modo LDAP / Active Directory
# ---------------------------------------------------------------------------
def _escapar_ldap(valor: str) -> str:
    """Escapa os caracteres especiais de um filtro LDAP (RFC 4515)."""
    substituicoes = {
        "\\": r"\5c",
        "*": r"\2a",
        "(": r"\28",
        ")": r"\29",
        "\x00": r"\00",
    }
    return "".join(substituicoes.get(ch, ch) for ch in valor)


def _procurar_ldap(termo: str, limite: int) -> list[dict]:
    """Pesquisa no Active Directory.

    A Base DN, se não vier explícita em LDAP_BASE_DN, é derivada de
    LDAP_DOMAIN (ex.: "mz.sbicdirectory.com" -> "DC=mz,DC=sbicdirectory,
    DC=com") — ver app/utils/active_directory.py.

    Requer no ambiente:
        LDAP_HOST, LDAP_BIND_DN, LDAP_BIND_PASSWORD
        (opcionais: LDAP_BASE_DN, LDAP_DOMAIN, LDAP_PORT, LDAP_USE_SSL,
        LDAP_DIRECTORY_FILTER)
    """
    try:
        from ldap3 import ALL, SUBTREE, Connection, Server
        from ldap3.core.exceptions import LDAPException
    except ImportError:  # pragma: no cover
        current_app.logger.error(
            "DIRECTORY_MODE=ldap mas o pacote 'ldap3' não está instalado."
        )
        return []

    from app.utils.active_directory import DOMINIO_OMISSAO, dominio_para_base_dn

    cfg = current_app.config
    host = cfg.get("LDAP_HOST")
    base_dn = cfg.get("LDAP_BASE_DN") or dominio_para_base_dn(cfg.get("LDAP_DOMAIN") or DOMINIO_OMISSAO)
    bind_dn = cfg.get("LDAP_BIND_DN")
    bind_pw = cfg.get("LDAP_BIND_PASSWORD")
    if not (host and bind_dn and bind_pw):
        current_app.logger.error(
            "Pesquisa no diretório: faltam LDAP_HOST / LDAP_BIND_DN / LDAP_BIND_PASSWORD."
        )
        return []

    termo_esc = _escapar_ldap(termo)
    # O AD desta instituição nem sempre tem o atributo "mail" preenchido — o
    # userPrincipalName (frequentemente já com formato de e-mail) é a
    # alternativa fiável (confirmado na biblioteca interna jactive-directory,
    # que identifica o utilizador só por sAMAccountName/userPrincipalName,
    # nunca por "mail"). Por isso a pesquisa e os atributos pedidos cobrem
    # os dois.
    filtro = cfg.get("LDAP_DIRECTORY_FILTER") or (
        "(&(objectClass=user)(objectCategory=person)"
        "(|(mail=*{q}*)(userPrincipalName=*{q}*)(displayName=*{q}*)(sAMAccountName={q}*)))"
    )
    filtro = filtro.replace("{q}", termo_esc)

    servidor = Server(
        host,
        port=cfg.get("LDAP_PORT", 636),
        use_ssl=cfg.get("LDAP_USE_SSL", True),
        get_info=ALL,
        connect_timeout=8,
    )
    try:
        conexao = Connection(
            servidor,
            user=bind_dn,
            password=bind_pw,
            auto_bind=True,
            receive_timeout=8,
        )
    except LDAPException:
        current_app.logger.exception(
            "Pesquisa no diretório: não foi possível ligar ao Active Directory."
        )
        return []

    try:
        conexao.search(
            base_dn,
            filtro,
            search_scope=SUBTREE,
            attributes=[
                "mail",
                "userPrincipalName",
                "displayName",
                "givenName",
                "sn",
                "department",
                "title",
                "sAMAccountName",
            ],
            size_limit=limite,
        )
        pessoas: list[dict] = []
        for entrada in conexao.entries:
            email = str(entrada.mail) if "mail" in entrada and entrada.mail else ""
            if not email and "userPrincipalName" in entrada and entrada.userPrincipalName:
                email = str(entrada.userPrincipalName)
            if not email:
                continue
            if "displayName" in entrada and entrada.displayName:
                nome = str(entrada.displayName)
            else:
                partes = [
                    str(entrada.givenName) if "givenName" in entrada and entrada.givenName else "",
                    str(entrada.sn) if "sn" in entrada and entrada.sn else "",
                ]
                nome = " ".join(p for p in partes if p) or email
            pessoas.append(
                {
                    "email": email,
                    "nome": nome,
                    "departamento": str(entrada.department) if "department" in entrada else "",
                    "cargo": str(entrada.title) if "title" in entrada else "",
                    "username": str(entrada.sAMAccountName) if "sAMAccountName" in entrada else "",
                    "origem": "ldap",
                }
            )
        return pessoas
    except LDAPException:
        current_app.logger.exception("Pesquisa no diretório: erro na pesquisa LDAP.")
        return []
    finally:
        try:
            conexao.unbind()
        except Exception:  # pragma: no cover
            pass
