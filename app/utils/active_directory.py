"""Ligação ao Active Directory do Standard Bank Moçambique.

A forma correta de ligar foi confirmada a partir da biblioteca interna do
banco `jactive-directory` (Java, `stdbank.common:jactive-directory-api`/
`-impl`, v1.0.0), decompilada e desassemblada byte a byte:

* Domínio por omissão, hardcoded no construtor de `Domain`:
      mz.sbicdirectory.com
* "Principal" da ligação (bind): "<username>@<dominio>" (estilo
  userPrincipalName), NÃO "<DOMINIO>\\<username>" (NTLM) — a implementação
  Java usa `java.naming.security.principal`/`...credentials` diretamente,
  o que corresponde a uma bind SIMPLE, não NTLM.
* Base DN derivada do domínio, convertendo cada rótulo separado por "." em
  "DC=<rótulo>": mz.sbicdirectory.com -> DC=mz,DC=sbicdirectory,DC=com
  (função `toDC` da classe `SessionImpl`).
* Atributos pedidos ao AD (classe `SessionImpl`):
      distinguishedName, cn, name, uid, sn, givenName, memberOf,
      sAMAccountName, userPrincipalName
* Filtro para encontrar um utilizador específico:
      (&(sAMAccountName=<valor>)(objectClass=user))

Nota de segurança: a biblioteca Java de 2019 liga sempre por "ldap://"
(texto limpo), sem TLS — aqui preferimos sempre LDAPS (`LDAP_USE_SSL=1`,
porta 636), enviando a password cifrada, independentemente do que a
biblioteca antiga fazia.
"""

from __future__ import annotations

DOMINIO_OMISSAO = "mz.sbicdirectory.com"


def dominio_para_base_dn(dominio: str) -> str:
    """Converte um domínio de DNS em Base DN LDAP.

    Replica exatamente `SessionImpl.toDC()` da jactive-directory:
    "mz.sbicdirectory.com" -> "DC=mz,DC=sbicdirectory,DC=com".
    """
    rotulos = [r for r in (dominio or "").split(".") if r]
    return ",".join(f"DC={r}" for r in rotulos)


def montar_principal(username: str, dominio: str) -> str:
    """Principal de bind no formato userPrincipalName: "username@dominio"."""
    return f"{(username or '').strip()}@{dominio}"
