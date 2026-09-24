"""Repositório de utilizadores sobre MongoDB (coleção ``users``).

O objeto devolvido — :class:`MongoUser` — expõe a mesma interface que
``app.models.user.User`` (métodos ``is_admin`` … e helpers do Flask-Login),
para que a fase 3 do plano de migração possa trocar a origem dos dados sem
mexer nas rotas nem nos templates.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories.base import get_db
from app.utils.constants import Perfil


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalizar_username(valor) -> str:
    return (valor or "").strip().upper()


class MongoUser(UserMixin):
    """Espelha ``app.models.user.User`` a partir de um documento Mongo."""

    def __init__(self, doc: dict):
        self._doc = doc
        self.id = str(doc["_id"])
        self.nome = doc.get("nome")
        self.email = doc.get("email")
        self.username = doc.get("username")
        self.password_hash = doc.get("password_hash")
        self.perfil = doc.get("perfil", Perfil.TECNICO.value)
        self.ativo = bool(doc.get("ativo", True))
        self.data_criacao = doc.get("data_criacao")
        assinatura = doc.get("assinatura") or {}
        self.assinatura_path = assinatura.get("path")
        self.assinatura_reutilizavel = bool(assinatura.get("reutilizavel", False))

    @property
    def nome_exibicao(self) -> str:
        """Nome real, ou o nº de colaborador até ao primeiro login."""
        return self.nome or self.username

    # -- Flask-Login -------------------------------------------------------
    def get_id(self) -> str:
        return self.id

    @property
    def is_active(self) -> bool:
        return self.ativo

    # -- paridade com o modelo SQLAlchemy --------------------------------
    def definir_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def verificar_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_admin(self) -> bool:
        return self.perfil == Perfil.ADMINISTRADOR.value

    def is_tecnico(self) -> bool:
        return self.perfil in (Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value)

    def is_aprovador(self) -> bool:
        return self.perfil == Perfil.APROVADOR.value

    def is_tecnico_admin(self) -> bool:
        return self.perfil == Perfil.TECNICO_ADMIN.value

    def pode_gerir_plataforma(self) -> bool:
        return self.is_admin() or self.is_tecnico_admin()

    # -- desnormalização em notas_saida --------------------------------
    def to_ref(self) -> dict:
        """Sub-documento ``{user_id, username, nome}`` para embutir nas notas."""
        return {
            "user_id": self._doc["_id"],
            "username": self.username,
            "nome": self.nome_exibicao,
        }

    def __repr__(self) -> str:
        return f"<MongoUser {self.username} ({self.perfil})>"


class UserRepository:
    COLLECTION = "users"

    def __init__(self, db=None):
        self._db = db

    @property
    def col(self):
        db = self._db if self._db is not None else get_db()
        return db[self.COLLECTION]

    # -- leitura --------------------------------------------------------
    def get(self, user_id) -> MongoUser | None:
        try:
            oid = ObjectId(str(user_id))
        except (InvalidId, TypeError):
            return None
        doc = self.col.find_one({"_id": oid})
        return MongoUser(doc) if doc else None

    def get_by_username(self, username: str) -> MongoUser | None:
        doc = self.col.find_one({"username": normalizar_username(username)})
        return MongoUser(doc) if doc else None

    def listar(self, pesquisa: str | None = None) -> list[MongoUser]:
        filtro: dict = {}
        if pesquisa:
            rx = {"$regex": pesquisa.strip(), "$options": "i"}
            filtro = {"$or": [{"nome": rx}, {"username": rx}]}
        return [MongoUser(d) for d in self.col.find(filtro).sort("nome", 1)]

    def username_disponivel(self, username: str, excepto_id=None) -> bool:
        doc = self.col.find_one({"username": normalizar_username(username)})
        if doc is None:
            return True
        return excepto_id is not None and str(doc["_id"]) == str(excepto_id)

    # -- escrita ------------------------------------------------------
    def criar(
        self,
        *,
        username: str,
        perfil: str,
        nome: str | None = None,
        email: str | None = None,
        ativo: bool = True,
        password: str | None = None,
        assinatura_path: str | None = None,
        assinatura_reutilizavel: bool = False,
    ) -> MongoUser:
        doc = {
            "nome": (nome or "").strip() or None,
            "email": (email or "").strip().lower() or None,
            "username": normalizar_username(username),
            "password_hash": generate_password_hash(password) if password else None,
            "perfil": perfil,
            "ativo": bool(ativo),
            "data_criacao": _agora_utc(),
            "assinatura": {
                "path": assinatura_path,
                "reutilizavel": bool(assinatura_reutilizavel),
            },
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return MongoUser(doc)

    def atualizar(self, user_id, campos: dict) -> MongoUser | None:
        self.col.update_one({"_id": ObjectId(str(user_id))}, {"$set": campos})
        return self.get(user_id)

    def definir_password(self, user_id, password: str) -> MongoUser | None:
        return self.atualizar(
            user_id, {"password_hash": generate_password_hash(password)}
        )

    def definir_estado(self, user_id, ativo: bool) -> MongoUser | None:
        return self.atualizar(user_id, {"ativo": bool(ativo)})

    def apagar(self, user_id) -> bool:
        try:
            oid = ObjectId(str(user_id))
        except (InvalidId, TypeError):
            return False
        resultado = self.col.delete_one({"_id": oid})
        return resultado.deleted_count == 1

    def upsert_demo(
        self, *, nome: str, username: str, perfil: str, password: str
    ) -> MongoUser:
        """Cria ou repõe uma conta de demonstração (usado pelo seed_mongo)."""
        username = normalizar_username(username)
        existente = self.col.find_one({"username": username})
        if existente:
            self.col.update_one(
                {"_id": existente["_id"]},
                {
                    "$set": {
                        "nome": nome,
                        "perfil": perfil,
                        "ativo": True,
                        "password_hash": generate_password_hash(password),
                    }
                },
            )
            return self.get_by_username(username)
        return self.criar(nome=nome, username=username, perfil=perfil, password=password)
