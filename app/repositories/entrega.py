"""Repositório MongoDB para a Nota de Entrega — mesmo padrão de
app/repositories/notas.py (adaptadores que espelham o SQLAlchemy), com
as diferenças próprias deste tipo: coluna DESTINO por item, e a
assinatura de Segurança com o seu próprio utilizador/data (seguranca_por
/ data_seguranca), além do papel genérico partilhado com a Saída.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.repositories.base import get_db
from app.repositories.counters import proximo_valor
from app.utils.constants import EstadoNota

PAPEIS_ASSINATURA = ("entregue", "aprovador", "recebido", "seguranca")


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


def _as_object_id(valor):
    if isinstance(valor, ObjectId):
        return valor
    try:
        return ObjectId(str(valor))
    except (InvalidId, TypeError):
        return valor


class _PessoaRefMongoEntrega:
    """Ver _PessoaRefMongo em repositories/notas.py — mesma ideia."""

    def __init__(self, id_=None, username=None, nome=None):
        self.id = id_
        self.username = username
        self.nome = nome

    def __bool__(self):
        return bool(self.nome or self.id)


class _ItemEntregaMongoAdapter:
    """Espelha app.models.item_entrega.ItemEntrega."""

    def __init__(self, doc: dict):
        self._doc = doc
        self.id = doc.get("_id")
        self.tipo_item = doc.get("tipo_item")
        self.destino = doc.get("destino")
        self.descricao = doc.get("descricao")
        self.numero_serie = doc.get("numero_serie")
        self.numero_sap = doc.get("numero_sap")
        self.quantidade = doc.get("quantidade", 1)

    def descricao_impressa(self):
        serie = self.numero_serie or "N/A"
        sap = self.numero_sap or "N/A"
        return f"{self.descricao} — Nr. Série: {serie} | SAP: {sap}"


class _EventoHistoricoEntregaMongo:
    """Espelha app.models.historico_entrega.HistoricoEntrega."""

    def __init__(self, doc: dict):
        self.utilizador = doc.get("utilizador")
        self.acao = doc.get("acao")
        self.data_hora = doc.get("data_hora")


class _NotaEntregaMongoAdapter:
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
        self.origem_local = doc.get("origem_local", "Sede IT")
        self.local_emissao = doc.get("local_emissao", "Maputo")
        self.numero_sequencial = doc.get("numero_sequencial")
        self.ano = doc.get("ano")

        self.criador = _PessoaRefMongoEntrega(self.criado_por, doc.get("criador_username"), doc.get("criador_nome"))
        self.aprovador = _PessoaRefMongoEntrega(self.aprovado_por, doc.get("aprovador_username"), doc.get("aprovador_nome"))
        self.seguranca = _PessoaRefMongoEntrega(self.seguranca_por, doc.get("seguranca_username"), doc.get("seguranca_nome"))
        self.revisao_tecnico = _PessoaRefMongoEntrega(
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

    # -- paridade de leitura ------------------------------------------------
    @property
    def numero_documento(self):
        ano = self.data_emissao.year if self.data_emissao else 2026
        numero = self.numero_sequencial or 0
        return f"{numero:06d}/{ano}"

    @property
    def numero_remedy(self):
        import re

        digitos = re.sub(r"\D", "", self.numero_referencia or "")
        return f"REQ{digitos}" if digitos else "REQ"

    @property
    def historico(self):
        from datetime import datetime as _dt
        return [_EventoHistoricoEntregaMongo(d) for d in sorted(
            self._historico_docs, key=lambda d: d.get("data_hora") or _to_utc(_dt.min), reverse=True
        )]

    @property
    def ultima_alteracao(self):
        eventos = self.historico
        return eventos[0].data_hora if eventos else self.data_criacao

    @property
    def assinaturas_entrega_ok(self):
        return bool(self.assinatura_entregue_path)

    @property
    def numero_assinaturas(self):
        return sum(
            1
            for p in (
                self.assinatura_entregue_path,
                self.assinatura_recebido_path,
                self.assinatura_aprovador_path,
                self.assinatura_seguranca_path,
            )
            if p
        )

    # -- regras de negócio (idênticas a NotaEntrega) ------------------------
    def pode_editar(self, utilizador):
        if not utilizador.is_authenticated:
            return False
        if self.estado not in {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
        }:
            return False
        return str(utilizador.id) == str(self.criado_por) or (
            self.revisao_tecnico_id is not None and str(self.revisao_tecnico_id) == str(utilizador.id)
        )

    def pode_submeter(self, utilizador):
        if self.estado not in {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
        }:
            return False
        if not self.pode_editar(utilizador):
            return False
        return self.assinaturas_entrega_ok

    def pode_gerir_assinaturas(self, utilizador):
        if not utilizador.is_authenticated:
            return False
        if self.estado not in {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
            EstadoNota.APROVADA.value,
        }:
            return False
        return utilizador.is_tecnico() and (
            str(utilizador.id) == str(self.criado_por)
            or (self.revisao_tecnico_id is not None and str(self.revisao_tecnico_id) == str(utilizador.id))
        )

    def pode_recolher_recebido(self, utilizador):
        return (
            self.estado == EstadoNota.APROVADA.value
            and not self.assinatura_recebido_path
            and self.pode_gerir_assinaturas(utilizador)
        )

    def pode_recolher_seguranca(self, utilizador):
        return not self.assinatura_seguranca_path and self.pode_gerir_assinaturas(utilizador)

    def pode_aprovar(self, utilizador):
        return self.estado == EstadoNota.PENDENTE_APROVACAO.value and utilizador.is_aprovador()

    def __repr__(self):
        return f"<_NotaEntregaMongoAdapter {self.numero_referencia} ({self.estado})>"


class MongoEntregaRepository:
    COLLECTION = "notas_entrega"
    CONTADOR = "notas_entrega"

    def __init__(self, db=None):
        self._db = db

    @property
    def col(self):
        db = self._db if self._db is not None else get_db()
        return db[self.COLLECTION]

    # -- criação / leitura ---------------------------------------------
    def criar(self, *, numero_referencia, data_emissao, funcionario, email_funcionario,
              departamento, motivo, observacao=None, origem_local="Sede IT",
              local_emissao="Maputo", criado_por, criador_nome=None, criador_username=None,
              itens=None, estado=None) -> _NotaEntregaMongoAdapter:
        ano = data_emissao.year if data_emissao else datetime.now(timezone.utc).year
        numero_sequencial = proximo_valor(f"{self.CONTADOR}_{ano}")
        doc = {
            "numero_referencia": (numero_referencia or "").strip(),
            "data_emissao": _to_utc(data_emissao),
            "ano": ano,
            "numero_sequencial": numero_sequencial,
            "funcionario": funcionario.strip(),
            "email_funcionario": (email_funcionario or "").strip().lower(),
            "departamento": departamento.strip(),
            "motivo": motivo,
            "observacao": (observacao or "").strip() or None,
            "origem_local": (origem_local or "Sede IT").strip(),
            "local_emissao": (local_emissao or "Maputo").strip(),
            "estado": estado or EstadoNota.RASCUNHO.value,
            "criado_por": criado_por,
            "criador_nome": criador_nome,
            "criador_username": criador_username,
            "aprovado_por": None,
            "seguranca_por": None,
            "revisao_tecnico_id": None,
            "data_aprovacao": None,
            "data_seguranca": None,
            "data_criacao": _to_utc(datetime.now(timezone.utc)),
            "data_conclusao": None,
            "pdf_path": None,
            "pdf_carregado": False,
            "comentario_decisao": None,
            "itens": [
                {
                    "_id": ObjectId(),
                    "tipo_item": item.get("tipo_item", "Outro"),
                    "destino": item.get("destino") or None,
                    "descricao": (item.get("descricao") or "").strip(),
                    "numero_serie": item.get("numero_serie") or None,
                    "numero_sap": item.get("numero_sap") or None,
                    "quantidade": max(int(item.get("quantidade", 1) or 1), 1),
                }
                for item in (itens or [])
                if (item.get("descricao") or "").strip()
            ],
            "assinaturas": {p: {} for p in PAPEIS_ASSINATURA},
            "historico": [],
        }
        doc["_id"] = self.col.insert_one(doc).inserted_id
        return _NotaEntregaMongoAdapter(doc)

    def obter_por_id(self, nota_id) -> _NotaEntregaMongoAdapter | None:
        doc = self.col.find_one({"_id": _as_object_id(nota_id)})
        return _NotaEntregaMongoAdapter(doc) if doc else None

    def listar(self, filtro: dict | None = None) -> list[_NotaEntregaMongoAdapter]:
        return [_NotaEntregaMongoAdapter(d) for d in self.col.find(filtro or {}).sort("data_criacao", -1)]

    def contar(self, filtro: dict | None = None) -> int:
        return self.col.count_documents(filtro or {})

    # -- escrita ---------------------------------------------------------
    def _set(self, nota_id, campos: dict) -> _NotaEntregaMongoAdapter:
        self.col.update_one({"_id": _as_object_id(nota_id)}, {"$set": campos})
        return self.obter_por_id(nota_id)

    def atualizar_dados(self, nota_id, *, numero_referencia, data_emissao, funcionario,
                         email_funcionario, departamento, motivo, observacao=None,
                         origem_local="Sede IT", local_emissao="Maputo", itens=None) -> _NotaEntregaMongoAdapter:
        campos = {
            "numero_referencia": (numero_referencia or "").strip(),
            "data_emissao": _to_utc(data_emissao),
            "funcionario": funcionario.strip(),
            "email_funcionario": (email_funcionario or "").strip().lower(),
            "departamento": departamento.strip(),
            "motivo": motivo,
            "observacao": (observacao or "").strip() or None,
            "origem_local": (origem_local or "Sede IT").strip(),
            "local_emissao": (local_emissao or "Maputo").strip(),
        }
        if itens is not None:
            campos["itens"] = [
                {
                    "_id": ObjectId(),
                    "tipo_item": item.get("tipo_item", "Outro"),
                    "destino": item.get("destino") or None,
                    "descricao": (item.get("descricao") or "").strip(),
                    "numero_serie": item.get("numero_serie") or None,
                    "numero_sap": item.get("numero_sap") or None,
                    "quantidade": max(int(item.get("quantidade", 1) or 1), 1),
                }
                for item in itens
                if (item.get("descricao") or "").strip()
            ]
        return self._set(nota_id, campos)

    def adicionar_historico(self, nota_id, utilizador_nome: str | None, acao: str):
        evento = {
            "utilizador": utilizador_nome or "Sistema",
            "acao": acao,
            "data_hora": _to_utc(datetime.now(timezone.utc)),
        }
        self.col.update_one({"_id": _as_object_id(nota_id)}, {"$push": {"historico": evento}})

    def definir_assinatura(self, nota_id, papel: str, *, path=None, posicao=None, limpar=False):
        if limpar:
            self.col.update_one(
                {"_id": _as_object_id(nota_id)},
                {"$set": {f"assinaturas.{papel}": {}}},
            )
            return
        campos = {}
        if path is not None:
            campos[f"assinaturas.{papel}.path"] = path
        if posicao:
            for eixo in ("x", "y", "w", "h"):
                campos[f"assinaturas.{papel}.{eixo}"] = posicao[eixo]
        if campos:
            self.col.update_one({"_id": _as_object_id(nota_id)}, {"$set": campos})

    def submeter(self, nota_id):
        self.col.update_one(
            {"_id": _as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.PENDENTE_APROVACAO.value,
                "comentario_decisao": None,
                "revisao_tecnico_id": None,
            }},
        )

    def aprovar(self, nota_id, *, aprovado_por, comentario=None, aprovador_nome=None, aprovador_username=None):
        self.col.update_one(
            {"_id": _as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.APROVADA.value,
                "aprovado_por": aprovado_por,
                "aprovador_nome": aprovador_nome,
                "aprovador_username": aprovador_username,
                "data_aprovacao": _to_utc(datetime.now(timezone.utc)),
                "comentario_decisao": comentario or None,
            }},
        )

    def definir_seguranca(self, nota_id, *, seguranca_por, seguranca_nome=None, seguranca_username=None):
        self.col.update_one(
            {"_id": _as_object_id(nota_id)},
            {"$set": {
                "seguranca_por": seguranca_por,
                "seguranca_nome": seguranca_nome,
                "seguranca_username": seguranca_username,
                "data_seguranca": _to_utc(datetime.now(timezone.utc)),
            }},
        )

    def concluir(self, nota_id, *, pdf_path):
        self.col.update_one(
            {"_id": _as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.CONCLUIDA.value,
                "data_conclusao": _to_utc(datetime.now(timezone.utc)),
                "pdf_path": pdf_path,
            }},
        )

    def rejeitar(self, nota_id, *, aprovado_por, comentario=None, aprovador_nome=None, aprovador_username=None):
        self.col.update_one(
            {"_id": _as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.REJEITADA.value,
                "aprovado_por": aprovado_por,
                "aprovador_nome": aprovador_nome,
                "aprovador_username": aprovador_username,
                "data_aprovacao": _to_utc(datetime.now(timezone.utc)),
                "comentario_decisao": comentario or None,
            }},
        )

    def devolver_para_revisao(self, nota_id, *, tecnico_id, motivo, tecnico_nome=None, tecnico_username=None):
        self.col.update_one(
            {"_id": _as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.EM_REVISAO.value,
                "revisao_tecnico_id": tecnico_id,
                "revisao_tecnico_nome": tecnico_nome,
                "revisao_tecnico_username": tecnico_username,
                "comentario_decisao": motivo,
                "aprovado_por": None,
                "aprovador_nome": None,
                "data_aprovacao": None,
                "assinaturas.aprovador": {},
            }},
        )

    def definir_pdf(self, nota_id, pdf_path, *, carregado=False):
        self.col.update_one(
            {"_id": _as_object_id(nota_id)},
            {"$set": {"pdf_path": pdf_path, "pdf_carregado": carregado}},
        )

    def apagar(self, nota_id) -> bool:
        resultado = self.col.delete_one({"_id": _as_object_id(nota_id)})
        return resultado.deleted_count == 1

    def dashboard(self, criado_por=None) -> tuple[dict, list[_NotaEntregaMongoAdapter]]:
        filtro = {"criado_por": criado_por} if criado_por is not None else {}
        stats = {
            "total": self.col.count_documents(filtro),
            "rascunho": self.col.count_documents({**filtro, "estado": EstadoNota.RASCUNHO.value}),
            "pendentes": self.col.count_documents({**filtro, "estado": EstadoNota.PENDENTE_APROVACAO.value}),
            "em_revisao": self.col.count_documents({**filtro, "estado": EstadoNota.EM_REVISAO.value}),
            "rejeitadas": self.col.count_documents({**filtro, "estado": EstadoNota.REJEITADA.value}),
            "aprovadas": self.col.count_documents({**filtro, "estado": EstadoNota.APROVADA.value}),
            "concluidas": self.col.count_documents({**filtro, "estado": EstadoNota.CONCLUIDA.value}),
        }
        recentes = [_NotaEntregaMongoAdapter(d) for d in self.col.find(filtro).sort("data_criacao", -1).limit(7)]
        return stats, recentes
