"""Devolução de equipamento associada a uma nota concluída (Saída ou Entrega).

Não gera documento: apenas regista, por item, que o equipamento voltou —
quando, quem registou, o estado do equipamento, o motivo e uma observação.

Armazenamento:
  - SQLite: tabela `devolucoes` (um registo por item devolvido);
  - MongoDB: campo `devolucoes` dentro do documento da própria nota.
Vários itens devolvidos no mesmo momento partilham o mesmo `registo_id`.

Estado de devolução de uma nota concluída:
  "nenhuma" (verde) · "parcial" (laranja) · "total" (cinzento)

Notas carregadas (só PDF, sem lista de itens) usam o modo MANUAL: o técnico
escreve o equipamento devolvido e indica se todo o material foi devolvido
(«completa»), já que a plataforma não consegue contar o que falta.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime

from app.utils.constants import EstadoNota

MOTIVOS = [
    "Saída do colaborador",
    "Substituição",
    "Avaria",
    "Fim de projeto / empréstimo",
    "Mudança de função",
    "Outro",
]
ESTADOS_EQUIPAMENTO = ["Bom", "Danificado", "Avariado"]


def _mongo(tipo: str) -> bool:
    flag = "USE_MONGO_NOTAS" if tipo == "saida" else "USE_MONGO_ENTREGA"
    return os.environ.get(flag, "0").strip().lower() in {"1", "true", "yes", "on"}


def _e_mongo(nota) -> bool:
    return hasattr(nota, "_doc")


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def _registos_brutos(tipo: str, nota) -> list[dict]:
    """Uma entrada por item devolvido, normalizada (ids como texto)."""
    if _e_mongo(nota):
        return [
            {
                "item_id": str(d.get("item_id")),
                "registo_id": d.get("registo_id"),
                "data": d.get("data"),
                "registado_por_nome": d.get("registado_por_nome"),
                "estado_equipamento": d.get("estado_equipamento"),
                "motivo": d.get("motivo"),
                "observacao": d.get("observacao"),
                "tipo_item": d.get("tipo_item"),
                "descricao": d.get("descricao"),
                "numero_serie": d.get("numero_serie"),
                "quantidade": d.get("quantidade"),
                "completa": bool(d.get("completa")),
            }
            for d in (nota._doc.get("devolucoes") or [])
        ]
    from app.models.devolucao import Devolucao

    return [
        {
            "item_id": d.item_id,
            "registo_id": d.registo_id,
            "data": d.data,
            "registado_por_nome": d.registado_por_nome,
            "estado_equipamento": d.estado_equipamento,
            "motivo": d.motivo,
            "observacao": d.observacao,
            "tipo_item": d.tipo_item,
            "descricao": d.descricao,
            "numero_serie": d.numero_serie,
            "quantidade": d.quantidade,
            "completa": bool(d.completa),
        }
        for d in Devolucao.query.filter_by(nota_tipo=tipo, nota_id=str(nota.id)).all()
    ]


def modo_manual(nota) -> bool:
    """Nota sem lista de itens (ex.: nota carregada a partir de um PDF)."""
    return not (getattr(nota, "itens", None) or [])


def _item_manual(r: dict) -> dict:
    return {
        "id": "",
        "tipo_item": r.get("tipo_item") or "",
        "descricao": r.get("descricao") or "",
        "numero_serie": r.get("numero_serie") or "",
        "quantidade": r.get("quantidade") or 1,
        "devolvido": True,
        "data_devolucao": r["data"].strftime("%d/%m/%Y") if r.get("data") else "",
    }


def devolucao_completa(tipo: str, nota) -> bool:
    return any(r.get("completa") for r in _registos_brutos(tipo, nota))


def itens_com_estado(tipo: str, nota) -> list[dict]:
    devolvidos = {r["item_id"]: r for r in _registos_brutos(tipo, nota)}
    itens = []
    for item in getattr(nota, "itens", None) or []:
        chave = str(item.id)
        reg = devolvidos.get(chave)
        itens.append({
            "id": chave,
            "tipo_item": item.tipo_item or "",
            "descricao": item.descricao or "",
            "numero_serie": item.numero_serie or "",
            "quantidade": item.quantidade or 1,
            "devolvido": reg is not None,
            "data_devolucao": reg["data"].strftime("%d/%m/%Y") if reg and reg.get("data") else "",
        })
    return itens


def estado_devolucao(tipo: str, nota) -> str | None:
    """None se a nota não estiver concluída ou não tiver itens."""
    if getattr(nota, "estado", None) != EstadoNota.CONCLUIDA.value:
        return None
    try:
        if modo_manual(nota):
            registos_nota = _registos_brutos(tipo, nota)
            if not registos_nota:
                return "nenhuma"
            return "total" if any(r.get("completa") for r in registos_nota) else "parcial"
        itens = itens_com_estado(tipo, nota)
    except Exception:  # noqa: BLE001 — nunca partir a listagem por causa disto
        return None
    if not itens:
        return None
    devolvidos = sum(1 for i in itens if i["devolvido"])
    if devolvidos == 0:
        return "nenhuma"
    return "total" if devolvidos == len(itens) else "parcial"


def registos(tipo: str, nota) -> list[dict]:
    """Devoluções agrupadas por momento de registo (mais recente primeiro)."""
    itens = {i["id"]: i for i in itens_com_estado(tipo, nota)}
    grupos: dict[str, dict] = {}
    for r in _registos_brutos(tipo, nota):
        g = grupos.setdefault(r["registo_id"], {
            "data": r["data"], "registado_por": r["registado_por_nome"] or "—",
            "motivo": r["motivo"] or "", "estado_equipamento": r["estado_equipamento"] or "",
            "observacao": r["observacao"] or "", "itens": [], "completa": False,
        })
        g["completa"] = g["completa"] or bool(r.get("completa"))
        item = _item_manual(r) if r.get("tipo_item") else itens.get(r["item_id"])
        if item:
            g["itens"].append(item)
    return sorted(grupos.values(), key=lambda g: g["data"] or datetime.min, reverse=True)


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------
def pode_registar(utilizador, nota) -> bool:
    return (
        getattr(nota, "estado", None) == EstadoNota.CONCLUIDA.value
        and getattr(utilizador, "is_tecnico", lambda: False)()
    )


def _validar_comum(utilizador, nota, motivo, estado_equipamento, observacao):
    if not pode_registar(utilizador, nota):
        raise PermissionError("Só técnicos podem registar devoluções de notas concluídas.")
    motivo = (motivo or "").strip()
    estado_equipamento = (estado_equipamento or "").strip()
    if motivo not in MOTIVOS:
        raise ValueError("Escolha o motivo da devolução.")
    if estado_equipamento not in ESTADOS_EQUIPAMENTO:
        raise ValueError("Indique o estado do equipamento.")
    observacao = (observacao or "").strip()[:500] or None
    if motivo == "Outro" and not observacao:
        raise ValueError("Descreva o motivo na observação.")
    return motivo, estado_equipamento, observacao


def _gravar(tipo, nota, utilizador, linhas, motivo, estado_equipamento, observacao, completa=False):
    """Grava as linhas (uma por item) partilhando o mesmo registo_id."""
    from app.utils.tempo import agora

    registo_id = uuid.uuid4().hex
    nome = getattr(utilizador, "nome_exibicao", None) or getattr(utilizador, "username", "")
    base = {"registo_id": registo_id, "data": agora(), "registado_por_id": str(utilizador.id),
            "registado_por_nome": nome, "estado_equipamento": estado_equipamento,
            "motivo": motivo, "observacao": observacao, "completa": bool(completa)}
    if _e_mongo(nota):
        from app.repositories.mongo_common import as_object_id

        if tipo == "saida":
            from app.repositories.notas import MongoNotaRepository as Repo
        else:
            from app.repositories.entrega import MongoEntregaRepository as Repo
        docs = []
        for linha in linhas:
            doc = dict(base, **linha)
            if doc.get("item_id"):
                doc["item_id"] = as_object_id(doc["item_id"])
            docs.append(doc)
        Repo().col.update_one({"_id": as_object_id(nota.id)}, {"$push": {"devolucoes": {"$each": docs}}})
        nota._doc.setdefault("devolucoes", []).extend(docs)
    else:
        from app.extensions import db
        from app.models.devolucao import Devolucao

        for linha in linhas:
            db.session.add(Devolucao(nota_tipo=tipo, nota_id=str(nota.id), **dict(base, **linha)))
        db.session.commit()


def registar_manual(tipo: str, nota, utilizador, itens_manuais, motivo, estado_equipamento,
                    observacao=None, completa=False) -> str:
    """Nota carregada (sem itens): o técnico escreve o equipamento devolvido."""
    from app.utils.constants import TIPOS_ITEM

    motivo, estado_equipamento, observacao = _validar_comum(
        utilizador, nota, motivo, estado_equipamento, observacao)
    if devolucao_completa(tipo, nota):
        raise ValueError("Esta nota já tem a devolução completa registada.")
    linhas = []
    for bruto in itens_manuais or []:
        tipo_item = (bruto.get("tipo_item") or "").strip()
        descricao = (bruto.get("descricao") or "").strip()[:255]
        if not tipo_item and not descricao:
            continue  # linha vazia
        if tipo_item not in TIPOS_ITEM:
            raise ValueError("Escolha o tipo de cada equipamento devolvido.")
        if not descricao:
            raise ValueError("Escreva a descrição de cada equipamento devolvido.")
        try:
            quantidade = max(1, int(bruto.get("quantidade") or 1))
        except (TypeError, ValueError):
            raise ValueError("Quantidade inválida.") from None
        linhas.append({"item_id": "", "tipo_item": tipo_item, "descricao": descricao,
                       "numero_serie": (bruto.get("numero_serie") or "").strip()[:100] or None,
                       "quantidade": quantidade})
    if not linhas:
        raise ValueError("Acrescente pelo menos um equipamento devolvido.")
    _gravar(tipo, nota, utilizador, linhas, motivo, estado_equipamento, observacao, completa)
    _registar_historico(tipo, nota, utilizador, sum(l["quantidade"] for l in linhas), motivo,
                        completa=bool(completa))
    return estado_devolucao(tipo, nota)


def registar(tipo: str, nota, utilizador, item_ids, motivo, estado_equipamento, observacao=None) -> str:
    """Regista a devolução dos itens indicados. Devolve o novo estado."""
    motivo, estado_equipamento, observacao = _validar_comum(
        utilizador, nota, motivo, estado_equipamento, observacao)

    disponiveis = {i["id"] for i in itens_com_estado(tipo, nota) if not i["devolvido"]}
    escolhidos = [str(i) for i in (item_ids or []) if str(i) in disponiveis]
    if not escolhidos:
        raise ValueError("Selecione pelo menos um item por devolver.")

    _gravar(tipo, nota, utilizador, [{"item_id": i} for i in escolhidos],
            motivo, estado_equipamento, observacao)
    _registar_historico(tipo, nota, utilizador, len(escolhidos), motivo)
    return estado_devolucao(tipo, nota)


def _registar_historico(tipo, nota, utilizador, n, motivo, completa=False):
    try:
        acao = f"Registou a devolução de {n} item(ns). Motivo: {motivo}."
        if completa:
            acao += " Devolução completa."
        if tipo == "saida":
            from app.services import historico_service

            historico_service.registrar(nota, acao, utilizador)
        else:
            from app.services.entrega_service import registrar

            registrar(nota, acao, utilizador)
        if not _e_mongo(nota):
            from app.extensions import db

            db.session.commit()
    except Exception:  # noqa: BLE001 — o histórico é complementar
        from flask import current_app

        current_app.logger.exception("Devolução: falha ao registar no histórico.")
