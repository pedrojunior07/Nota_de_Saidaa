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

Nota sobre o servidor: a biblioteca `jactive-directory` NÃO tem nenhum
controlador de domínio (DC) fixo no código — `ConnectionInfo.serverName`
fica em aberto, para quem a usa configurar. Por isso `LDAP_HOST` nunca
deve ser um palpite: por omissão, este módulo descobre os DCs reais via
DNS (registo SRV `_ldap._tcp.dc._msdcs.<domínio>`) — a mesma forma como
qualquer computador Windows os encontra sozinho ao entrar no domínio.
`LDAP_HOST` só é necessário para forçar um servidor específico.
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


def descobrir_controladores(dominio: str) -> list[tuple[str, int]]:
    """Descobre os controladores de domínio via DNS (registos SRV), tal como
    qualquer computador Windows já faz sozinho ao entrar num domínio — sem
    precisar de saber o nome de nenhum servidor à partida.

    Consulta ``_ldap._tcp.dc._msdcs.<dominio>`` (o registo SRV padrão do
    Active Directory para localizar controladores de domínio) e devolve
    ``[(hostname, porta), ...]`` ordenados por prioridade e depois peso
    (RFC 2782: prioridade mais baixa primeiro; dentro da mesma prioridade,
    peso mais alto primeiro). Lista vazia se a consulta falhar (sem DNS
    interno acessível, domínio incorreto, biblioteca não instalada, etc.)
    — quem chama decide o que fazer nesse caso (ex.: usar LDAP_HOST manual).
    """
    if not dominio:
        return []
    try:
        import dns.resolver
    except ImportError:  # pragma: no cover
        return []

    consulta = f"_ldap._tcp.dc._msdcs.{dominio}"
    try:
        respostas = dns.resolver.resolve(consulta, "SRV", lifetime=5)
    except Exception:  # pragma: no cover — qualquer falha de DNS: NXDOMAIN, timeout, sem rede
        return []

    ordenados = sorted(respostas, key=lambda r: (r.priority, -r.weight))
    return [(str(r.target).rstrip("."), r.port) for r in ordenados]


def obter_candidatos_ldap(dominio: str, host_configurado: str | None) -> list[tuple[str, int | None]]:
    """Lista de (host, porta) a tentar, por ordem, para ligar ao AD.

    Se ``LDAP_HOST`` estiver definido explicitamente no ambiente, é usado
    tal e qual (substitui a descoberta automática — útil para apontar a um
    controlador de domínio específico, ou em testes). Caso contrário,
    descobre os controladores reais via DNS SRV; se a descoberta falhar
    (sem resultados), cai para o próprio nome do domínio como último
    recurso — muitas zonas de AD também respondem em LDAP no nome do
    domínio em si.
    """
    if host_configurado:
        return [(host_configurado, None)]
    descobertos = descobrir_controladores(dominio)
    if descobertos:
        return descobertos
    return [(dominio, None)]
