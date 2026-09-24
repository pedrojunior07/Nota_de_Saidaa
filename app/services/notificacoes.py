"""Notificações por e-mail do fluxo das notas (Saída e Entrega).

Quando se envia:
  - Nota submetida para aprovação  -> o Aprovador escolhido pelo técnico
                                      (notas antigas sem escolha: todos os
                                      Aprovadores ativos).
  - Nota aprovada                  -> o técnico que criou a nota.
  - Nota rejeitada                 -> o técnico que criou a nota e, se o
                                      Aprovador escolheu outro, esse técnico.
  - Nota concluída                 -> o recetor (e-mail «Para» da nota), com o
                                      PDF em anexo, enviado em nome do técnico
                                      que recolheu a assinatura «Recebido».

Os e-mails de fluxo são curtos de propósito: dizem o que aconteceu e trazem o
link para a nota — os detalhes vêem-se no sistema.

Regras de robustez:
  - Nunca levanta exceções para quem chama: uma falha de e-mail não pode
    impedir aprovar/concluir uma nota. Tudo o que falha fica no log.
  - O envio SMTP corre numa thread (o pedido HTTP não espera pelo servidor
    de correio). Todos os dados (destinatários, textos, links, PDF) são
    recolhidos ANTES, ainda dentro do pedido.
  - MAIL_MODE=simulacao (omissão) só regista no log o que seria enviado.
"""

from __future__ import annotations

import logging
import os
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app, request, url_for

from app.utils.constants import Perfil

log = logging.getLogger(__name__)

_TIPOS = {
    "saida": {"nome": "Nota de Saída", "detalhe": "notas.detalhe"},
    "entrega": {"nome": "Nota de Entrega", "detalhe": "entrega.detalhe"},
}


# ---------------------------------------------------------------------------
# Destinatários
# ---------------------------------------------------------------------------
def _email_por_diretorio(username: str | None) -> str | None:
    if not username:
        return None
    try:
        from app.services.directory_service import procurar_pessoas

        for pessoa in procurar_pessoas(username, limite=5):
            if (pessoa.get("username") or "").upper() == username.upper():
                return (pessoa.get("email") or "").strip().lower() or None
    except Exception:  # noqa: BLE001 — o diretório é só um recurso
        log.exception("Falha ao procurar o e-mail de %s no diretório.", username)
    return None


def email_de(pessoa) -> str | None:
    """E-mail de um utilizador (User, MongoUser ou PessoaRefMongo).

    1) o e-mail guardado no perfil (login via API ou indicado pelo admin);
    2) o perfil completo, se ``pessoa`` for só uma referência (Mongo);
    3) o diretório de colaboradores, pelo nº de colaborador.
    """
    if not pessoa:
        return None
    email = getattr(pessoa, "email", None)
    if email:
        return email
    username = getattr(pessoa, "username", None)
    pessoa_id = getattr(pessoa, "id", None)
    if pessoa_id is not None and not hasattr(pessoa, "perfil"):
        completo = _obter_utilizador(pessoa_id)
        if completo is not None and getattr(completo, "email", None):
            return completo.email
        username = username or getattr(completo, "username", None)
    return _email_por_diretorio(username)


def _obter_utilizador(user_id):
    from app.services.auth_service import _mongo_users_ativo

    try:
        if _mongo_users_ativo():
            from app.repositories.users import UserRepository

            return UserRepository().get(user_id)
        from app.models.user import User
        from app.extensions import db

        return db.session.get(User, int(user_id))
    except Exception:  # noqa: BLE001
        log.exception("Falha ao obter o utilizador %s.", user_id)
        return None


def _aprovadores_ativos() -> list:
    from app.services.auth_service import _mongo_users_ativo

    if _mongo_users_ativo():
        from app.repositories.users import UserRepository

        todos = UserRepository().listar()
    else:
        from app.models.user import User

        todos = User.query.all()
    return [u for u in todos if u.perfil == Perfil.APROVADOR.value and u.ativo]


def _criador(nota):
    criador = getattr(nota, "criador", None)
    if criador:
        return criador
    return _obter_utilizador(getattr(nota, "criado_por", None))


def _aprovador_designado(nota):
    designado = getattr(nota, "aprovador_designado", None)
    if designado:
        return designado
    return _obter_utilizador(getattr(nota, "aprovador_designado_id", None))


def _tecnico_revisao(nota):
    tecnico = getattr(nota, "revisao_tecnico", None)
    if tecnico:
        return tecnico
    return _obter_utilizador(getattr(nota, "revisao_tecnico_id", None))


# ---------------------------------------------------------------------------
# Construção e envio
# ---------------------------------------------------------------------------
def _link(tipo: str, nota) -> str:
    endpoint = _TIPOS[tipo]["detalhe"]
    caminho = url_for(endpoint, nota_id=nota.id)
    base = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    if not base:
        base = request.url_root.rstrip("/") if request else ""
    return f"{base}{caminho}"


def _referencia(nota) -> str:
    return getattr(nota, "numero_referencia", None) or f"#{nota.id}"


def _nome(pessoa) -> str:
    return getattr(pessoa, "nome_exibicao", None) or getattr(pessoa, "nome", None) or "—"


def _corpo(saudacao: str, linhas: list[str], link: str | None) -> str:
    partes = [saudacao, "", *linhas]
    if link:
        partes += ["", f"Para ver os detalhes, entre no sistema: {link}"]
    partes += ["", "Esta é uma mensagem automática — não responda a este e-mail."]
    return "\n".join(partes)


def _montar(para: list[str], assunto: str, corpo: str, *, remetente=None,
            responder_a=None, anexo: str | None = None) -> EmailMessage | None:
    para = sorted({p for p in para if p})
    if not para:
        return None
    cfg = current_app.config
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = remetente or cfg.get("MAIL_DEFAULT_SENDER") or "nao-responder@localhost"
    msg["To"] = ", ".join(para)
    if responder_a:
        msg["Reply-To"] = responder_a
    msg.set_content(corpo)
    if anexo:
        with open(anexo, "rb") as fh:
            msg.add_attachment(
                fh.read(), maintype="application", subtype="pdf",
                filename=os.path.basename(anexo),
            )
    return msg


def _enviar_smtp(msg: EmailMessage, cfg: dict) -> None:
    classe = smtplib.SMTP_SSL if cfg["MAIL_USE_SSL"] else smtplib.SMTP
    with classe(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=cfg["MAIL_TIMEOUT"]) as smtp:
        if cfg["MAIL_USE_TLS"] and not cfg["MAIL_USE_SSL"]:
            smtp.starttls()
        if cfg["MAIL_USERNAME"]:
            smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
        smtp.send_message(msg)


def _despachar(msg: EmailMessage | None, contexto: str) -> None:
    """Envia (ou simula) a mensagem sem bloquear o pedido nem lançar erros."""
    if msg is None:
        log.warning("Notificação '%s' sem destinatários com e-mail — não enviada.", contexto)
        return
    cfg = current_app.config
    modo = (cfg.get("MAIL_MODE") or "simulacao").lower()
    if modo == "desligado":
        return
    if modo != "smtp" or not cfg.get("MAIL_SERVER"):
        log.info(
            "[e-mail simulado] %s | De: %s | Para: %s | Assunto: %s\n%s",
            contexto, msg["From"], msg["To"], msg["Subject"],
            msg.get_body(preferencelist=("plain",)).get_content(),
        )
        return
    smtp_cfg = {k: cfg.get(k) for k in (
        "MAIL_SERVER", "MAIL_PORT", "MAIL_USE_TLS", "MAIL_USE_SSL",
        "MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_TIMEOUT",
    )}

    def _trabalho():
        try:
            _enviar_smtp(msg, smtp_cfg)
            log.info("E-mail enviado (%s) para %s.", contexto, msg["To"])
        except Exception:  # noqa: BLE001
            log.exception("Falha ao enviar e-mail (%s) para %s.", contexto, msg["To"])

    threading.Thread(target=_trabalho, name=f"email-{contexto}", daemon=True).start()


def _seguro(func):
    """Nenhuma notificação pode partir o fluxo da nota."""
    def _envolvida(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception:  # noqa: BLE001
            log.exception("Falha ao preparar a notificação %s.", func.__name__)
    _envolvida.__name__ = func.__name__
    _envolvida.__doc__ = func.__doc__
    return _envolvida


# ---------------------------------------------------------------------------
# API pública (chamada pelas rotas, depois de a ação ter sucesso)
# ---------------------------------------------------------------------------
@_seguro
def nota_submetida(tipo: str, nota, tecnico) -> None:
    """Nova nota à espera de aprovação -> o Aprovador escolhido."""
    nome_tipo = _TIPOS[tipo]["nome"]
    ref = _referencia(nota)
    designado = _aprovador_designado(nota)
    aprovadores = [designado] if designado else _aprovadores_ativos()
    para = [email_de(a) for a in aprovadores]
    corpo = _corpo(
        "Olá,",
        [f"Tem uma {nome_tipo} nova para aprovar: {ref}.",
         f"Submetida por: {_nome(tecnico)}."],
        _link(tipo, nota),
    )
    _despachar(_montar(para, f"{nome_tipo} {ref} — pendente de aprovação", corpo),
               f"{tipo}:submetida:{nota.id}")


@_seguro
def nota_decidida(tipo: str, nota, decisao: str, aprovador, comentario: str | None = None) -> None:
    """Feedback do Aprovador -> técnico(s). ``decisao``: "aprovada" ou "rejeitada"."""
    nome_tipo = _TIPOS[tipo]["nome"]
    ref = _referencia(nota)
    destinatarios = [_criador(nota)]
    if decisao == "rejeitada":
        destinatarios.append(_tecnico_revisao(nota))
        titulo = "rejeitada"
        linhas = [f"A {nome_tipo} {ref} foi rejeitada por {_nome(aprovador)}.",
                  "Pode corrigir a nota no sistema e voltar a submetê-la."]
    else:
        titulo = "aprovada"
        linhas = [f"A {nome_tipo} {ref} foi aprovada por {_nome(aprovador)}.",
                  "Falta recolher a assinatura de «Recebido» para a concluir."]
    if comentario:
        linhas.append(f"{'Motivo' if decisao == 'rejeitada' else 'Comentário'}: {comentario}")
    corpo = _corpo("Olá,", linhas, _link(tipo, nota))
    para = [email_de(d) for d in destinatarios if d]
    _despachar(_montar(para, f"{nome_tipo} {ref} — {titulo}", corpo),
               f"{tipo}:{decisao}:{nota.id}")


@_seguro
def nota_concluida(tipo: str, nota, tecnico) -> None:
    """Nota concluída -> recetor, com o PDF, em nome do técnico que recolheu
    a assinatura «Recebido»."""
    nome_tipo = _TIPOS[tipo]["nome"]
    ref = _referencia(nota)
    pdf = getattr(nota, "pdf_path", None)
    if not pdf or not os.path.isfile(pdf):
        log.warning("Nota %s concluída sem PDF em disco (%s) — e-mail não enviado.", nota.id, pdf)
        return

    email_tecnico = email_de(tecnico)
    cfg = current_app.config
    remetente, responder_a = None, email_tecnico
    if email_tecnico and cfg.get("MAIL_FROM_TECNICO"):
        remetente = formataddr((_nome(tecnico), email_tecnico))
        responder_a = None

    corpo = "\n".join([
        f"Caro(a) {getattr(nota, 'funcionario', None) or 'colaborador(a)'},",
        "",
        f"Segue em anexo a {nome_tipo} {ref}, já concluída e assinada.",
        "",
        "Cumprimentos,",
        _nome(tecnico),
    ])
    msg = _montar([getattr(nota, "email_funcionario", None)],
                  f"{nome_tipo} {ref}", corpo,
                  remetente=remetente, responder_a=responder_a, anexo=pdf)
    _despachar(msg, f"{tipo}:concluida:{nota.id}")
