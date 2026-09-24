"""Assinatura pessoal (reutilizável) do utilizador — uma só por pessoa.

É a mesma assinatura em todo o lado: bloco "Minha assinatura" da Nota de
Saída, da Nota de Entrega e da página do administrador a editar os próprios
dados. Um administrador que também é técnico vê e usa, portanto, sempre o
mesmo PNG (``sig_user_<id>.png``).

Este módulo concentra:
  - a leitura do PNG vindo do pedido (ficheiro carregado ou desenho no canvas);
  - a gravação no perfil, tanto em SQLite como em MongoDB
    (``USE_MONGO_USERS``) — antes as rotas só alteravam o objeto em memória e
    faziam ``db.session.commit()``, o que não persistia nada no Mongo.
"""

from __future__ import annotations

from flask import request

from app.extensions import db
from app.utils.assinatura import guardar_dataurl_png, guardar_png, remover_ficheiro

JA_EXISTE = "Já existe uma assinatura neste perfil. Elimine-a para carregar outra."


def nome_ficheiro_perfil(utilizador) -> str:
    return f"sig_user_{utilizador.id}.png"


def ler_png_do_pedido(utilizador):
    """Grava em disco o PNG enviado no pedido atual.

    Aceita multipart (campo ``signature``) ou JSON (campo ``imagem`` com um
    data URL). Devolve ``(fname, nota_id, erro)``.
    """
    nome_fixo = nome_ficheiro_perfil(utilizador)
    if "signature" in request.files:
        fname, erro = guardar_png(request.files["signature"], nome_fixo=nome_fixo)
        nota_id = request.form.get("nota_id") or None
    else:
        dados = request.get_json(silent=True) or {}
        fname, erro = guardar_dataurl_png(dados.get("imagem"), nome_fixo)
        nota_id = dados.get("nota_id") or None
    return fname, nota_id, erro


def definir_assinatura_perfil(utilizador, path: str | None) -> None:
    """Grava (ou limpa, se ``path`` for None) a assinatura no perfil.

    Não faz commit da sessão SQLAlchemy — quem chama decide (as rotas de
    notas/entrega juntam esta alteração à da nota no mesmo commit).
    """
    from app.services.auth_service import _mongo_users_ativo

    reutilizavel = bool(path)
    # Mantém o objeto em memória (current_user) coerente nos dois modos.
    utilizador.assinatura_path = path
    utilizador.assinatura_reutilizavel = reutilizavel
    if _mongo_users_ativo():
        from app.repositories.users import UserRepository

        UserRepository().atualizar(
            utilizador.id, {"assinatura": {"path": path, "reutilizavel": reutilizavel}}
        )


def apagar_assinatura_perfil(utilizador) -> None:
    """Limpa a assinatura do perfil e remove o ficheiro. Faz commit."""
    anterior = utilizador.assinatura_path
    definir_assinatura_perfil(utilizador, None)
    db.session.commit()
    if anterior:
        remover_ficheiro(anterior)
