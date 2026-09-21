"""Repositório MongoDB para a Nota de Saída, com adaptador que espelha a
interface do modelo SQLAlchemy (NotaSaida/ItemNota), para que rotas e
templates funcionem sem alterações, seja qual for a origem dos dados.

O que é comum à Nota de Entrega (utilitários, regras de negócio, CRUD
de transições de estado) vive em app/repositories/mongo_common.py —
aqui fica só o que é específico da Saída.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from app.repositories.mongo_common import (
    LOCAL_EMISSAO_OMISSAO,
    ORIGEM_LOCAL_OMISSAO,
    PAPEIS_ASSINATURA,
    BaseMongoNotaRepository,
    ItemMongoAdapterBase,
    NotaMongoAdapterMixin,
    PessoaRefMongo,
    doc_item,
    to_utc,
)
from app.utils.constants import EstadoNota


class _ItemMongoAdapter(ItemMongoAdapterBase):
    """Item da Nota de Saída — sem campos próprios além dos comuns."""


class _NotaMongoAdapter(NotaMongoAdapterMixin):
    """Espelha app.models.nota.NotaSaida a partir de um documento Mongo."""

    def __init__(self, doc: dict):
        self._doc = doc
        self.id = str(doc["_id"])
        self._oid = doc["_id"]
        self.numero_referencia = doc.get("numero_referencia")
        data_emissao = doc.get("data_emissao")
        self.data_emissao = data_emissao.date() if isinstance(data_emissao, datetime) else data_emissao
        self.funcionario = doc.get("funcionario")
        self.email_funcionario = doc.get("email_funcionario")
        self.departamento = doc.get("departamento")
        self.motivo = doc.get("motivo")
        self.observacao = doc.get("observacao")
        self.estado = doc.get("estado", EstadoNota.RASCUNHO.value)
        self.criado_por = doc.get("criado_por")
        self.aprovado_por = doc.get("aprovado_por")
        self.revisao_tecnico_id = doc.get("revisao_tecnico_id")
        self.data_aprovacao = doc.get("data_aprovacao")
        self.data_criacao = doc.get("data_criacao")
        self.data_conclusao = doc.get("data_conclusao")
        self.pdf_path = doc.get("pdf_path")
        self.pdf_carregado = bool(doc.get("pdf_carregado", False))
        self.comentario_decisao = doc.get("comentario_decisao")
        self.origem_local = doc.get("origem_local", ORIGEM_LOCAL_OMISSAO)
        self.local_emissao = doc.get("local_emissao", LOCAL_EMISSAO_OMISSAO)
        self.numero_sequencial = doc.get("numero_sequencial")
        self.ano = doc.get("ano")

        self.criador = PessoaRefMongo(self.criado_por, doc.get("criador_username"), doc.get("criador_nome"))
        self.aprovador = PessoaRefMongo(self.aprovado_por, doc.get("aprovador_username"), doc.get("aprovador_nome"))
        self.revisao_tecnico = PessoaRefMongo(
            self.revisao_tecnico_id, doc.get("revisao_tecnico_username"), doc.get("revisao_tecnico_nome")
        )

        assinaturas = doc.get("assinaturas") or {}
        for papel in PAPEIS_ASSINATURA:
            sub = assinaturas.get(papel) or {}
            setattr(self, f"assinatura_{papel}_path", sub.get("path"))
            setattr(self, f"assinatura_{papel}_x", sub.get("x"))
            setattr(self, f"assinatura_{papel}_y", sub.get("y"))
            setattr(self, f"assinatura_{papel}_w", sub.get("w"))
            setattr(self, f"assinatura_{papel}_h", sub.get("h"))

        self.itens = [_ItemMongoAdapter(i) for i in doc.get("itens", [])]
        self._historico_docs = doc.get("historico", [])


class MongoNotaRepository(BaseMongoNotaRepository):
    COLLECTION = "notas_saida"
    CONTADOR = "notas_saida"
    ADAPTER = _NotaMongoAdapter

    def criar(self, dados: dict, *, criado_por, criador_nome=None,
              criador_username=None, itens=None, estado=None) -> _NotaMongoAdapter:
        ano, numero_sequencial = self._proximo_numero_sequencial(dados["data_emissao"])
        doc = {
            "numero_referencia": (dados["numero_referencia"] or "").strip(),
            "data_emissao": to_utc(dados["data_emissao"]),
            "ano": ano,
            "numero_sequencial": numero_sequencial,
            "funcionario": dados["funcionario"].strip(),
            "email_funcionario": (dados["email_funcionario"] or "").strip().lower(),
            "departamento": dados["departamento"].strip(),
            "motivo": dados["motivo"],
            "observacao": (dados.get("observacao") or "").strip() or None,
            "origem_local": (dados.get("origem_local") or ORIGEM_LOCAL_OMISSAO).strip(),
            "local_emissao": (dados.get("local_emissao") or LOCAL_EMISSAO_OMISSAO).strip(),
            "estado": estado or EstadoNota.RASCUNHO.value,
            "criado_por": criado_por,
            "criador_nome": criador_nome,
            "criador_username": criador_username,
            "aprovado_por": None,
            "revisao_tecnico_id": None,
            "data_aprovacao": None,
            "data_criacao": to_utc(datetime.now(timezone.utc)),
            "data_conclusao": None,
            "pdf_path": None,
            "pdf_carregado": False,
            "comentario_decisao": None,
            "itens": [doc_item(item) for item in (itens or []) if (item.get("descricao") or "").strip()],
            "assinaturas": {p: {} for p in PAPEIS_ASSINATURA},
            "historico": [],
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return _NotaMongoAdapter(doc)

    def atualizar_dados(self, nota_id, dados: dict, *, itens=None) -> _NotaMongoAdapter:
        campos = {
            "numero_referencia": (dados["numero_referencia"] or "").strip(),
            "data_emissao": to_utc(dados["data_emissao"]),
            "funcionario": dados["funcionario"].strip(),
            "email_funcionario": (dados["email_funcionario"] or "").strip().lower(),
            "departamento": dados["departamento"].strip(),
            "motivo": dados["motivo"],
            "observacao": (dados.get("observacao") or "").strip() or None,
            "origem_local": (dados.get("origem_local") or ORIGEM_LOCAL_OMISSAO).strip(),
            "local_emissao": (dados.get("local_emissao") or LOCAL_EMISSAO_OMISSAO).strip(),
        }
        if itens is not None:
            campos["itens"] = [doc_item(item) for item in itens if (item.get("descricao") or "").strip()]
        return self._set(nota_id, campos)
