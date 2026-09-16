"""Camada de acesso a dados sobre MongoDB.

Esta camada é ADITIVA: coexiste com os modelos SQLAlchemy em app/models/ e,
por enquanto, nenhuma rota a utiliza. É o passo 2 ("repositórios") do plano de
migração descrito em docs/Modelo_de_Dados_e_Backend.docx.

Uso típico (scripts / testes / futura fase 3):

    from app.repositories.base import ensure_indexes
    from app.repositories.users import UserRepository

    ensure_indexes()
    utilizador = UserRepository().get_by_username("A200550")
"""

from app.repositories.base import ensure_indexes, get_db, reset_connection
from app.repositories.modulos import ModuloRepository
from app.repositories.notas import MongoNotaRepository
from app.repositories.users import MongoUser, UserRepository

__all__ = [
    "ensure_indexes",
    "get_db",
    "reset_connection",
    "ModuloRepository",
    "MongoNotaRepository",
    "MongoUser",
    "UserRepository",
]
