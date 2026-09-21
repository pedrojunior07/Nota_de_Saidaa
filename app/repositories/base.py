"""Ligação partilhada ao MongoDB e criação de índices.

Reutiliza app.services.mongo.MongoConnection (que já lê as variáveis
MONGO_URI / MONGO_USER / MONGO_PASSWORD / MONGO_DB_NAME do ambiente).
"""

from __future__ import annotations

import threading

from pymongo import ASCENDING, DESCENDING

from app.services.mongo import MongoConnection

_lock = threading.Lock()
_connection: MongoConnection | None = None


def get_connection() -> MongoConnection:
    """Devolve uma ligação MongoDB partilhada (criada à primeira chamada)."""
    global _connection
    if _connection is None:
        with _lock:
            if _connection is None:
                _connection = MongoConnection()
    return _connection


def get_db():
    """Handle da base de dados configurada (MONGO_DB_NAME)."""
    return get_connection().database()


def reset_connection() -> None:
    """Fecha e esquece a ligação atual. Usado sobretudo em testes."""
    global _connection
    with _lock:
        if _connection is not None:
            _connection.close()
        _connection = None


def ensure_indexes() -> None:
    """Cria os índices de todas as coleções. Idempotente (pode correr no arranque)."""
    db = get_db()

    db.users.create_index("username", unique=True, name="ux_users_username")
    db.users.create_index("perfil", name="ix_users_perfil")
    db.users.create_index("ativo", name="ix_users_ativo")

    db.modulos.create_index("ordem", name="ix_modulos_ordem")

    for colecao in ("notas_saida", "notas_entrega"):
        col = db[colecao]
        col.create_index(
            "numero_referencia", unique=True, name="ux_numero_referencia"
        )
        col.create_index("estado", name="ix_estado")
        col.create_index(
            [("ano", ASCENDING), ("numero_sequencial", ASCENDING)],
            unique=True,
            name="ux_ano_numero",
        )
        col.create_index("email_funcionario", name="ix_email_funcionario")
        col.create_index("criado_por", name="ix_criado_por")
        col.create_index("revisao_tecnico_id", name="ix_revisao_tecnico_id")
        col.create_index([("data_criacao", DESCENDING)], name="ix_data_criacao")
