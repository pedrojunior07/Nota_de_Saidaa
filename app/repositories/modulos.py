"""Catálogo de módulos sobre MongoDB (coleção ``modulos``).

Enquanto a fase 3 do plano de migração não ligar as rotas, o dicionário
``MODULOS`` em ``app/routes/modulos.py`` continua a ser a fonte de verdade em
runtime. O conteúdo deste catálogo tem de espelhar esse dicionário.
"""

from __future__ import annotations

from app.repositories.base import get_db

CATALOGO_INICIAL = [
    {
        "_id": "saida",
        "nome": "Nota de Saída",
        "descricao": (
            "Entrega de equipamento de TI a colaboradores, com fluxo de "
            "aprovação e assinatura digital."
        ),
        "icone": "bi-box-arrow-right",
        "ordem": 1,
        "disponivel": True,
        "blueprints": ["dashboard", "notas", "aprovacoes", "admin"],
    },
    {
        "_id": "entrega",
        "nome": "Nota de Entrega",
        "descricao": "Entrega de material a balcões e filiais. Módulo em preparação.",
        "icone": "bi-truck",
        "ordem": 2,
        "disponivel": True,
        "blueprints": ["entrega"],
    },
]


class ModuloRepository:
    COLLECTION = "modulos"

    def __init__(self, db=None):
        self._db = db

    @property
    def col(self):
        db = self._db if self._db is not None else get_db()
        return db[self.COLLECTION]

    def listar(self, apenas_disponiveis: bool = False) -> list[dict]:
        filtro = {"disponivel": True} if apenas_disponiveis else {}
        return list(self.col.find(filtro).sort("ordem", 1))

    def obter(self, chave: str) -> dict | None:
        return self.col.find_one({"_id": chave})

    def mapa_blueprint_para_modulo(self) -> dict[str, str]:
        return {
            bp: doc["_id"]
            for doc in self.col.find({})
            for bp in doc.get("blueprints", [])
        }

    def semear_catalogo(self) -> list[dict]:
        """Insere/atualiza o catálogo inicial. Idempotente."""
        for doc in CATALOGO_INICIAL:
            self.col.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
        return self.listar()
