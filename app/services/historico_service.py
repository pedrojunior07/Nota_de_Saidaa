"""Registo da trilha de auditoria."""

import os

from flask_login import current_user

from app.extensions import db
from app.models.historico import Historico
from app.repositories.notas import MongoNotaRepository


def _mongo_historico_ativo() -> bool:
    return os.environ.get("USE_MONGO_HISTORICO", "0").strip().lower() in {"1", "true", "yes", "on"}


def registrar(nota, acao, utilizador=None):
    """Acrescenta uma entrada de histórico associada à nota."""
    nome = "Sistema"
    if utilizador is not None:
        nome = getattr(utilizador, "nome", str(utilizador))
    elif current_user and getattr(current_user, "is_authenticated", False):
        nome = current_user.nome

    if _mongo_historico_ativo() or os.environ.get("USE_MONGO_NOTAS", "0").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            repo = MongoNotaRepository()
            return repo.adicionar_historico(nota.id, nome, acao)
        except Exception:
            pass

    entrada = Historico(nota_id=nota.id, utilizador=nome, acao=acao)
    db.session.add(entrada)
    return entrada
