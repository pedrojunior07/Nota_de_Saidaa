"""Utilitários e base partilhada pelos repositórios MongoDB de Nota de
Saída (notas.py) e Nota de Entrega (entrega.py) — os dois seguem
exatamente o mesmo padrão de documento/estado, só diferem nos campos
próprios de cada tipo (ex.: destino do item, assinatura de Segurança
com utilizador próprio).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.repositories.base import get_db
from app.repositories.counters import proximo_valor
from app.utils.constants import EstadoNota

PAPEIS_ASSINATURA = ("entregue", "aprovador", "recebido", "seguranca")
ORIGEM_LOCAL_OMISSAO = "Sede IT"
LOCAL_EMISSAO_OMISSAO = "Maputo"


def to_utc(value):
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


def as_object_id(valor):
    if isinstance(valor, ObjectId):
        return valor
    try:
        return ObjectId(str(valor))
    except (InvalidId, TypeError):
        return valor


class PessoaRefMongo:
    """Pequeno objeto com só `.nome`/`.id`/`.username`, para que o PDF e os
    templates possam continuar a escrever `nota.aprovador.nome` como já
    faziam com a relação SQLAlchemy — sem precisar de ir buscar o
    utilizador completo (o nome fica desnormalizado no próprio documento
    da nota, tal como o MongoUser.to_ref() já previa)."""

    def __init__(self, id_=None, username=None, nome=None):
        self.id = id_
        self.username = username
        self.nome = nome

    def __bool__(self):
        return bool(self.nome or self.id)


class EventoHistoricoMongo:
    """Espelha app.models.historico(_entrega).Historico a partir de um
    item do array embutido no documento da nota."""

    def __init__(self, doc: dict):
        self.utilizador = doc.get("utilizador")
        self.acao = doc.get("acao")
        self.data_hora = doc.get("data_hora")


class ItemMongoAdapterBase:
    """Campos comuns a um item de Saída ou Entrega. Subclasses acrescentam
    o que for próprio (ex.: `destino`, só na Entrega)."""

    def __init__(self, doc: dict):
        self._doc = doc
        self.id = doc.get("_id")
        self.tipo_item = doc.get("tipo_item")
        self.descricao = doc.get("descricao")
        self.numero_serie = doc.get("numero_serie")
        self.numero_sap = doc.get("numero_sap")
        self.quantidade = doc.get("quantidade", 1)

    def descricao_impressa(self):
        serie = self.numero_serie or "N/A"
        sap = self.numero_sap or "N/A"
        return f"{self.descricao} — Nr. Série: {serie} | SAP: {sap}"


def doc_item(item: dict, *, extra: dict | None = None) -> dict:
    """Sub-documento de item comum a Saída/Entrega, com os campos extra
    próprios de cada tipo (ex.: `destino`) fundidos por cima."""
    base = {
        "_id": ObjectId(),
        "tipo_item": item.get("tipo_item", "Outro"),
        "descricao": (item.get("descricao") or "").strip(),
        "numero_serie": item.get("numero_serie") or None,
        "numero_sap": item.get("numero_sap") or None,
        "quantidade": max(int(item.get("quantidade", 1) or 1), 1),
    }
    if extra:
        base.update(extra)
    return base


class NotaMongoAdapterMixin:
    """Regras de negócio e propriedades de leitura idênticas entre o
    adaptador de Nota de Saída e o de Entrega — cada subclasse só
    define os atributos no seu __init__ (criado_por, estado, etc.) e as
    diferenças próprias (ex.: pode_recolher_seguranca, só na Entrega)."""

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
        return [
            EventoHistoricoMongo(d)
            for d in sorted(
                self._historico_docs,
                key=lambda d: d.get("data_hora") or to_utc(datetime.min),
                reverse=True,
            )
        ]

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
                self.assinatura_seguranca_path,
                self.assinatura_aprovador_path,
            )
            if p
        )

    def pode_editar(self, utilizador):
        if not utilizador.is_authenticated:
            return False
        estados_editaveis = {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
        }
        if self.estado not in estados_editaveis:
            return False
        if str(utilizador.id) == str(self.criado_por):
            return True
        return self.revisao_tecnico_id is not None and str(self.revisao_tecnico_id) == str(utilizador.id)

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

    def pode_aprovar(self, utilizador):
        return self.estado == EstadoNota.PENDENTE_APROVACAO.value and utilizador.is_aprovador()

    def __repr__(self):
        return f"<{type(self).__name__} {self.numero_referencia} ({self.estado})>"


class BaseMongoNotaRepository:
    """CRUD/transições de estado partilhadas entre MongoNotaRepository e
    MongoEntregaRepository. Subclasses definem COLLECTION, CONTADOR e
    ADAPTER, e a sua própria criar()/atualizar_dados() (os campos-base
    são iguais, mas cada tipo acrescenta os seus — destino, segurança).
    """

    COLLECTION: str = ""
    CONTADOR: str = ""
    ADAPTER = None  # classe adaptadora (definida em cada subclasse)

    def __init__(self, db=None):
        self._db = db

    @property
    def col(self):
        db = self._db if self._db is not None else get_db()
        return db[self.COLLECTION]

    def _adaptar(self, doc):
        return self.ADAPTER(doc) if doc else None

    def _proximo_numero_sequencial(self, data_emissao) -> tuple[int, int]:
        ano = data_emissao.year if data_emissao else datetime.now(timezone.utc).year
        return ano, proximo_valor(f"{self.CONTADOR}_{ano}")

    # -- leitura ---------------------------------------------------------
    def obter_por_id(self, nota_id):
        return self._adaptar(self.col.find_one({"_id": as_object_id(nota_id)}))

    def listar(self, filtro: dict | None = None) -> list:
        return [self._adaptar(d) for d in self.col.find(filtro or {}).sort("data_criacao", -1)]

    def contar(self, filtro: dict | None = None) -> int:
        return self.col.count_documents(filtro or {})

    def dashboard(self, criado_por=None):
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
        recentes = [self._adaptar(d) for d in self.col.find(filtro).sort("data_criacao", -1).limit(7)]
        return stats, recentes

    # -- escrita comum -----------------------------------------------
    def _set(self, nota_id, campos: dict):
        self.col.update_one({"_id": as_object_id(nota_id)}, {"$set": campos})
        return self.obter_por_id(nota_id)

    def adicionar_historico(self, nota_id, utilizador_nome: str | None, acao: str):
        evento = {
            "utilizador": utilizador_nome or "Sistema",
            "acao": acao,
            "data_hora": to_utc(datetime.now(timezone.utc)),
        }
        self.col.update_one({"_id": as_object_id(nota_id)}, {"$push": {"historico": evento}})

    def definir_assinatura(self, nota_id, papel: str, *, path=None, posicao=None, limpar=False):
        if limpar:
            self.col.update_one({"_id": as_object_id(nota_id)}, {"$set": {f"assinaturas.{papel}": {}}})
            return
        campos = {}
        if path is not None:
            campos[f"assinaturas.{papel}.path"] = path
        if posicao:
            for eixo in ("x", "y", "w", "h"):
                campos[f"assinaturas.{papel}.{eixo}"] = posicao[eixo]
        if campos:
            self.col.update_one({"_id": as_object_id(nota_id)}, {"$set": campos})

    def submeter(self, nota_id):
        self.col.update_one(
            {"_id": as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.PENDENTE_APROVACAO.value,
                "comentario_decisao": None,
                "revisao_tecnico_id": None,
            }},
        )

    def aprovar(self, nota_id, *, aprovado_por, comentario=None, aprovador_nome=None, aprovador_username=None):
        self.col.update_one(
            {"_id": as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.APROVADA.value,
                "aprovado_por": aprovado_por,
                "aprovador_nome": aprovador_nome,
                "aprovador_username": aprovador_username,
                "data_aprovacao": to_utc(datetime.now(timezone.utc)),
                "comentario_decisao": comentario or None,
            }},
        )

    def concluir(self, nota_id, *, pdf_path):
        self.col.update_one(
            {"_id": as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.CONCLUIDA.value,
                "data_conclusao": to_utc(datetime.now(timezone.utc)),
                "pdf_path": pdf_path,
            }},
        )

    def rejeitar(self, nota_id, *, aprovado_por, comentario=None, aprovador_nome=None, aprovador_username=None):
        self.col.update_one(
            {"_id": as_object_id(nota_id)},
            {"$set": {
                "estado": EstadoNota.REJEITADA.value,
                "aprovado_por": aprovado_por,
                "aprovador_nome": aprovador_nome,
                "aprovador_username": aprovador_username,
                "data_aprovacao": to_utc(datetime.now(timezone.utc)),
                "comentario_decisao": comentario or None,
            }},
        )

    def devolver_para_revisao(self, nota_id, *, tecnico_id, motivo, tecnico_nome=None, tecnico_username=None):
        self.col.update_one(
            {"_id": as_object_id(nota_id)},
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
            {"_id": as_object_id(nota_id)},
            {"$set": {"pdf_path": pdf_path, "pdf_carregado": carregado}},
        )

    def apagar(self, nota_id) -> bool:
        resultado = self.col.delete_one({"_id": as_object_id(nota_id)})
        return resultado.deleted_count == 1
