"""Repositório MongoDB para a Nota de Entrega — mesmo padrão de
app/repositories/notas.py (partilham utilitários, regras de negócio e
CRUD de transições de estado via app/repositories/mongo_common.py).
Aqui fica só o que é próprio da Entrega: o campo DESTINO por item, e a
assinatura de Segurança com o seu próprio utilizador/data
(seguranca_por / data_seguranca), além do papel genérico partilhado.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.mongo_common import (
    LOCAL_EMISSAO_OMISSAO,
    ORIGEM_LOCAL_OMISSAO,
    PAPEIS_ASSINATURA,
    BaseMongoNotaRepository,
    ItemMongoAdapterBase,
    NotaMongoAdapterMixin,
    PessoaRefMongo,
    as_object_id,
    doc_item,
    to_utc,
)
from app.utils.constants import EstadoNota


class _ItemEntregaMongoAdapter(ItemMongoAdapterBase):
    """Item da Nota de Entrega — acrescenta o destino ao que é comum."""

    def __init__(self, doc: dict):
        super().__init__(doc)
        self.destino = doc.get("destino")


class _NotaEntregaMongoAdapter(NotaMongoAdapterMixin):
    """Espelha app.models.nota_entrega.NotaEntrega a partir de um documento Mongo."""

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
        self.seguranca_por = doc.get("seguranca_por")
        self.revisao_tecnico_id = doc.get("revisao_tecnico_id")
        self.data_aprovacao = doc.get("data_aprovacao")
        self.data_seguranca = doc.get("data_seguranca")
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
        self.seguranca = PessoaRefMongo(self.seguranca_por, doc.get("seguranca_username"), doc.get("seguranca_nome"))
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

        self.itens = [_ItemEntregaMongoAdapter(i) for i in doc.get("itens", [])]
        self._historico_docs = doc.get("historico", [])

    def pode_recolher_seguranca(self, utilizador):
        return not self.assinatura_seguranca_path and self.pode_gerir_assinaturas(utilizador)


class MongoEntregaRepository(BaseMongoNotaRepository):
    COLLECTION = "notas_entrega"
    CONTADOR = "notas_entrega"
    ADAPTER = _NotaEntregaMongoAdapter

    def criar(self, dados: dict, *, criado_por, criador_nome=None,
              criador_username=None, itens=None, estado=None) -> _NotaEntregaMongoAdapter:
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
            "seguranca_por": None,
            "revisao_tecnico_id": None,
            "data_aprovacao": None,
            "data_seguranca": None,
            "data_criacao": to_utc(datetime.now(timezone.utc)),
            "data_conclusao": None,
            "pdf_path": None,
            "pdf_carregado": False,
            "comentario_decisao": None,
            "itens": [
                doc_item(item, extra={"destino": item.get("destino") or None})
                for item in (itens or [])
                if (item.get("descricao") or "").strip()
            ],
            "assinaturas": {p: {} for p in PAPEIS_ASSINATURA},
            "historico": [],
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return _NotaEntregaMongoAdapter(doc)

    def atualizar_dados(self, nota_id, dados: dict, *, itens=None) -> _NotaEntregaMongoAdapter:
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
            campos["itens"] = [
                doc_item(item, extra={"destino": item.get("destino") or None})
                for item in itens
                if (item.get("descricao") or "").strip()
            ]
        return self._set(nota_id, campos)

    def definir_seguranca(self, nota_id, *, seguranca_por, seguranca_nome=None, seguranca_username=None):
        self.col.update_one(
            {"_id": as_object_id(nota_id)},
            {"$set": {
                "seguranca_por": seguranca_por,
                "seguranca_nome": seguranca_nome,
                "seguranca_username": seguranca_username,
                "data_seguranca": to_utc(datetime.now(timezone.utc)),
            }},
        )
