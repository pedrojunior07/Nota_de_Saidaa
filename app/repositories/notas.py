"""Repositório MongoDB para notas de saída."""

from __future__ import annotations

from datetime import date, datetime, timezone
import re

from app.repositories.base import get_db
from app.utils.constants import EstadoNota


REMEDY_PATTERN = re.compile(r"^REQ\d{12}$")


def validar_numero_referencia(valor: str) -> str:
    numero = (valor or "").strip().upper()
    if not REMEDY_PATTERN.fullmatch(numero):
        raise ValueError("O numero Remedy deve ter o formato REQ000006253074.")
    return numero


def _to_utc(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, datetime.min.time())
    else:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class MongoNotaRepository:
    COLLECTION = "notas_saida"

    def __init__(self, db=None):
        self._db = db

    @property
    def col(self):
        db = self._db if self._db is not None else get_db()
        return db[self.COLLECTION]

    def criar(
        self,
        *,
        numero_referencia: str,
        data_emissao,
        funcionario: str,
        email_funcionario: str,
        departamento: str,
        motivo: str,
        observacao: str | None = None,
        origem_local: str = "Sede IT",
        local_emissao: str = "Maputo",
        criado_por=None,
        itens: list[dict] | None = None,
        estado: str = EstadoNota.RASCUNHO.value,
    ) -> dict:
        numero_referencia = validar_numero_referencia(numero_referencia)
        doc = {
            "numero_referencia": numero_referencia.strip(),
            "data_emissao": _to_utc(data_emissao),
            "funcionario": funcionario.strip(),
            "email_funcionario": (email_funcionario or "").strip().lower(),
            "departamento": departamento.strip(),
            "motivo": motivo,
            "observacao": (observacao or "").strip() or None,
            "origem": {"local": origem_local.strip(), "local_emissao": local_emissao.strip()},
            "estado": estado,
            "criado_por": {"user_id": criado_por, "username": str(criado_por)} if criado_por else None,
            "datas": {
                "criacao": _to_utc(datetime.now(timezone.utc)),
                "aprovacao": None,
                "conclusao": None,
            },
            "itens": [
                {
                    "tipo_item": item.get("tipo_item", "Outro"),
                    "descricao": item.get("descricao", "").strip(),
                    "numero_serie": item.get("numero_serie") or None,
                    "quantidade": max(int(item.get("quantidade", 1) or 1), 1),
                }
                for item in (itens or [])
                if item.get("descricao", "").strip()
            ],
            "assinaturas": {
                "entregue": None,
                "recebido": None,
                "seguranca": None,
                "aprovador": None,
            },
            "historico": [],
            "pdf_path": None,
            "comentario_decisao": None,
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return doc

    def contar(self) -> int:
        return self.col.count_documents({})

    def apagar(self, nota_id) -> bool:
        resultado = self.col.delete_one({"_id": self._as_object_id(nota_id)})
        return resultado.deleted_count == 1

    def obter_por_numero_referencia(self, numero_referencia: str) -> dict | None:
        return self.col.find_one({"numero_referencia": numero_referencia})

    def obter_por_id(self, nota_id) -> dict | None:
        try:
            from bson import ObjectId
            return self.col.find_one({"_id": ObjectId(str(nota_id))})
        except Exception:
            return self.col.find_one({"_id": nota_id})

    def listar(self, filtro: dict | None = None, *, order_by: str = "datas.criacao") -> list[dict]:
        query = filtro or {}
        return list(self.col.find(query).sort(order_by, -1))

    def dashboard(self, criado_por=None) -> tuple[dict, list[dict]]:
        filtro = {}
        if criado_por is not None:
            filtro = {
                "$or": [
                    {"criado_por.user_id": criado_por},
                    {"criado_por.username": criado_por},
                ]
            }

        stats = {
            "total": self.col.count_documents(filtro),
            "rascunho": self.col.count_documents({**filtro, "estado": EstadoNota.RASCUNHO.value}),
            "pendentes": self.col.count_documents({**filtro, "estado": EstadoNota.PENDENTE_APROVACAO.value}),
            "em_revisao": self.col.count_documents({**filtro, "estado": EstadoNota.EM_REVISAO.value}),
            "rejeitadas": self.col.count_documents({**filtro, "estado": EstadoNota.REJEITADA.value}),
            "aprovadas": self.col.count_documents({**filtro, "estado": EstadoNota.APROVADA.value}),
            "concluidas": self.col.count_documents({**filtro, "estado": EstadoNota.CONCLUIDA.value}),
        }
        recentes = list(self.col.find(filtro).sort("datas.criacao", -1).limit(7))
        return stats, recentes

    def atualizar(self, nota_id, campos: dict) -> dict | None:
        self.col.update_one({"_id": self._as_object_id(nota_id)}, {"$set": campos})
        return self.obter_por_id(nota_id)

    def _as_object_id(self, nota_id):
        try:
            from bson import ObjectId
            return ObjectId(str(nota_id))
        except Exception:
            return nota_id

    def adicionar_historico(self, nota_id, utilizador_nome: str, acao: str):
        evento = {
            "utilizador": utilizador_nome,
            "acao": acao,
            "data_hora": _to_utc(datetime.now(timezone.utc)),
        }
        self.col.update_one(
            {"_id": self._as_object_id(nota_id)},
            {"$push": {"historico": evento}},
        )
        return evento

    def submeter_para_aprovacao(self, nota_id):
        self.col.update_one(
            {"_id": self._as_object_id(nota_id)},
            {"$set": {"estado": EstadoNota.PENDENTE_APROVACAO.value}},
        )

    def aprovar(self, nota_id, *, comentario=None, aprovado_por=None, data_aprovacao=None):
        agora = _to_utc(data_aprovacao or datetime.now(timezone.utc))
        payload = {
            "estado": EstadoNota.CONCLUIDA.value,
            "comentario_decisao": comentario,
            "aprovado_por": aprovado_por,
            "datas.aprovacao": agora,
            "datas.conclusao": agora,
        }
        self.col.update_one({"_id": self._as_object_id(nota_id)}, {"$set": payload})

    def rejeitar(self, nota_id, *, comentario=None, aprovado_por=None):
        payload = {
            "estado": EstadoNota.REJEITADA.value,
            "comentario_decisao": comentario,
            "aprovado_por": aprovado_por,
            "datas.aprovacao": _to_utc(datetime.now(timezone.utc)),
        }
        self.col.update_one({"_id": self._as_object_id(nota_id)}, {"$set": payload})

    def devolver_para_revisao(self, nota_id, *, tecnico_id=None, motivo=None):
        self.col.update_one(
            {"_id": self._as_object_id(nota_id)},
            {
                "$set": {
                    "estado": EstadoNota.EM_REVISAO.value,
                    "revisao_tecnico_id": tecnico_id,
                    "comentario_decisao": motivo,
                    "aprovado_por": None,
                }
            },
        )
