"""Migração única dos dados de SQLite (SQLAlchemy) para o MongoDB.

Lê a base relacional atual (instance/nota_saida.db, via create_app) e escreve
nas coleções e no formato exatos que app/repositories/{notas,entrega,users}.py
já usam em produção (o mesmo que as rotas leem/escrevem quando USE_MONGO_*=1):

    users, notas_saida (itens/assinaturas/historico embutidos, com
    criador_nome/aprovador_nome/... desnormalizados), notas_entrega
    (idem, com o campo destino por item e a assinatura de Segurança),
    counters (contador por tipo+ano, usado para numero_documento)

Nota: os "campos adicionais" dinâmicos (ValorCampoDinamico) NÃO precisam de
migração — ficam onde estão (SQL), já que essa tabela guarda o
documento_id como String e funciona identicamente com um id SQL ou Mongo
(ver app/services/campos_dinamicos_service.py).

Uso:
    python -m scripts.migrate_sqlite_to_mongo --dry-run   # só conta, não escreve
    python -m scripts.migrate_sqlite_to_mongo             # escreve (recusa se já houver dados)
    python -m scripts.migrate_sqlite_to_mongo --limpar    # apaga as coleções alvo e reescreve

Requer as variáveis MONGO_* no .env (ver .env.example).
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId

from app import create_app
from app.models.historico import Historico
from app.models.historico_entrega import HistoricoEntrega
from app.models.item_entrega import ItemEntrega
from app.models.nota import NotaSaida
from app.models.nota_entrega import NotaEntrega
from app.models.user import User
from app.repositories.base import ensure_indexes, get_db
from app.repositories.modulos import ModuloRepository

MAPUTO = ZoneInfo("Africa/Maputo")
COLECOES_ALVO = ["users", "notas_saida", "notas_entrega", "counters", "modulos"]
PAPEIS_SAIDA = ("entregue", "aprovador", "recebido", "seguranca")
PAPEIS_ENTREGA = ("entregue", "aprovador", "recebido", "seguranca")


def to_utc(valor):
    """Converte um datetime/date ingénuo (hora de Maputo) para datetime UTC."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        dt = valor
    elif isinstance(valor, date):
        dt = datetime(valor.year, valor.month, valor.day)
    else:
        return valor
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MAPUTO)
    return dt.astimezone(timezone.utc)


def _assinatura(nota, prefixo):
    path = getattr(nota, f"assinatura_{prefixo}_path", None)
    if not path:
        return {}
    campo = {"path": path}
    for eixo in ("x", "y", "w", "h"):
        valor = getattr(nota, f"assinatura_{prefixo}_{eixo}", None)
        if valor is not None:
            campo[eixo] = valor
    return campo


def migrar(dry_run: bool = False, limpar: bool = False) -> None:
    app = create_app("development")
    # Em dry-run não tocamos no MongoDB (nem sequer exigimos as variáveis MONGO_*).
    db = None if dry_run else get_db()

    if limpar and not dry_run:
        for nome in COLECOES_ALVO:
            db[nome].drop()
        print("Coleções alvo apagadas:", ", ".join(COLECOES_ALVO))

    if not dry_run and not limpar and db.users.estimated_document_count():
        raise SystemExit(
            "A coleção 'users' já tem documentos. Use --limpar para reescrever "
            "ou --dry-run para simular."
        )

    with app.app_context():
        utilizadores = User.query.order_by(User.id).all()
        notas_saida = NotaSaida.query.order_by(NotaSaida.id).all()
        notas_entrega = NotaEntrega.query.order_by(NotaEntrega.id).all()

        # -- users ---------------------------------------------------------
        # Formato identico ao que app/repositories/users.py (UserRepository/
        # MongoUser) le/escreve - nao mexer sem atualizar os dois a par.
        ref_por_id: dict[int, dict] = {}
        docs_users = []
        for u in utilizadores:
            doc = {
                "nome": u.nome,
                "username": (u.username or "").strip().upper(),
                "password_hash": u.password_hash,
                "perfil": u.perfil,
                "ativo": bool(u.ativo),
                "data_criacao": to_utc(u.data_criacao),
                "assinatura": {
                    "path": u.assinatura_path,
                    "reutilizavel": bool(u.assinatura_reutilizavel),
                },
            }
            docs_users.append((u.id, doc))

        print(f"users .............. {len(docs_users)}")
        if not dry_run and docs_users:
            for old_id, doc in docs_users:
                res = db.users.insert_one(doc)
                ref_por_id[old_id] = {
                    "_id": res.inserted_id,
                    "username": doc["username"],
                    "nome": doc["nome"],
                }
        elif dry_run:
            for old_id, doc in docs_users:
                ref_por_id[old_id] = {
                    "_id": None,
                    "username": doc["username"],
                    "nome": doc["nome"],
                }

        def ref(user_id):
            return ref_por_id.get(user_id)

        # -- notas_saida ----------------------------------------------------
        # Formato identico ao que app/repositories/notas.py
        # (MongoNotaRepository/_NotaMongoAdapter) le/escreve.
        contadores_saida: dict[int, int] = {}
        docs_notas_saida = []
        total_itens = total_hist = 0
        for n in notas_saida:
            ano = n.data_emissao.year if n.data_emissao else 2026
            contadores_saida[ano] = max(contadores_saida.get(ano, 0), n.id)
            criador = ref(n.criado_por)
            aprovador = ref(n.aprovado_por)
            revisor = ref(n.revisao_tecnico_id)
            historico = [
                {
                    "utilizador": h.utilizador,
                    "acao": h.acao,
                    "data_hora": to_utc(h.data_hora),
                }
                for h in n.historico.order_by(Historico.data_hora).all()
            ]
            itens = [
                {
                    "_id": ObjectId(),
                    "tipo_item": it.tipo_item,
                    "descricao": it.descricao,
                    "numero_serie": it.numero_serie,
                    "numero_sap": it.numero_sap,
                    "quantidade": it.quantidade,
                }
                for it in n.itens
            ]
            total_itens += len(itens)
            total_hist += len(historico)
            docs_notas_saida.append(
                {
                    "numero_referencia": n.numero_referencia,
                    "data_emissao": to_utc(n.data_emissao),
                    "ano": ano,
                    "numero_sequencial": n.id,
                    "funcionario": n.funcionario,
                    "email_funcionario": n.email_funcionario,
                    "departamento": n.departamento,
                    "motivo": n.motivo,
                    "observacao": n.observacao,
                    "origem_local": n.origem_local,
                    "local_emissao": n.local_emissao,
                    "estado": n.estado,
                    "criado_por": criador["_id"] if criador else None,
                    "criador_nome": criador["nome"] if criador else None,
                    "criador_username": criador["username"] if criador else None,
                    "aprovado_por": aprovador["_id"] if aprovador else None,
                    "aprovador_nome": aprovador["nome"] if aprovador else None,
                    "aprovador_username": aprovador["username"] if aprovador else None,
                    "revisao_tecnico_id": revisor["_id"] if revisor else None,
                    "revisao_tecnico_nome": revisor["nome"] if revisor else None,
                    "revisao_tecnico_username": revisor["username"] if revisor else None,
                    "data_aprovacao": to_utc(n.data_aprovacao),
                    "data_criacao": to_utc(n.data_criacao),
                    "data_conclusao": to_utc(n.data_conclusao),
                    "pdf_path": n.pdf_path,
                    "pdf_carregado": bool(n.pdf_carregado),
                    "comentario_decisao": n.comentario_decisao,
                    "itens": itens,
                    "assinaturas": {p: _assinatura(n, p) for p in PAPEIS_SAIDA},
                    "historico": historico,
                }
            )

        print(f"notas_saida ........ {len(docs_notas_saida)}  "
              f"(itens embutidos: {total_itens}, eventos de histórico: {total_hist})")
        if not dry_run and docs_notas_saida:
            db.notas_saida.insert_many(docs_notas_saida)

        # -- notas_entrega ---------------------------------------------------
        # Formato identico ao que app/repositories/entrega.py
        # (MongoEntregaRepository/_NotaEntregaMongoAdapter) le/escreve.
        contadores_entrega: dict[int, int] = {}
        docs_notas_entrega = []
        total_itens_e = total_hist_e = 0
        for n in notas_entrega:
            ano = n.data_emissao.year if n.data_emissao else 2026
            contadores_entrega[ano] = max(contadores_entrega.get(ano, 0), n.id)
            criador = ref(n.criado_por)
            aprovador = ref(n.aprovado_por)
            seguranca = ref(getattr(n, "seguranca_por", None))
            revisor = ref(n.revisao_tecnico_id)
            historico = [
                {
                    "utilizador": h.utilizador,
                    "acao": h.acao,
                    "data_hora": to_utc(h.data_hora),
                }
                for h in n.historico.order_by(HistoricoEntrega.data_hora).all()
            ]
            itens = [
                {
                    "_id": ObjectId(),
                    "tipo_item": it.tipo_item,
                    "destino": getattr(it, "destino", None),
                    "descricao": it.descricao,
                    "numero_serie": it.numero_serie,
                    "numero_sap": it.numero_sap,
                    "quantidade": it.quantidade,
                }
                for it in n.itens
            ]
            total_itens_e += len(itens)
            total_hist_e += len(historico)
            docs_notas_entrega.append(
                {
                    "numero_referencia": n.numero_referencia,
                    "data_emissao": to_utc(n.data_emissao),
                    "ano": ano,
                    "numero_sequencial": n.id,
                    "funcionario": n.funcionario,
                    "email_funcionario": n.email_funcionario,
                    "departamento": n.departamento,
                    "motivo": n.motivo,
                    "observacao": n.observacao,
                    "origem_local": n.origem_local,
                    "local_emissao": n.local_emissao,
                    "estado": n.estado,
                    "criado_por": criador["_id"] if criador else None,
                    "criador_nome": criador["nome"] if criador else None,
                    "criador_username": criador["username"] if criador else None,
                    "aprovado_por": aprovador["_id"] if aprovador else None,
                    "aprovador_nome": aprovador["nome"] if aprovador else None,
                    "aprovador_username": aprovador["username"] if aprovador else None,
                    "seguranca_por": seguranca["_id"] if seguranca else None,
                    "seguranca_nome": seguranca["nome"] if seguranca else None,
                    "seguranca_username": seguranca["username"] if seguranca else None,
                    "revisao_tecnico_id": revisor["_id"] if revisor else None,
                    "revisao_tecnico_nome": revisor["nome"] if revisor else None,
                    "revisao_tecnico_username": revisor["username"] if revisor else None,
                    "data_aprovacao": to_utc(n.data_aprovacao),
                    "data_seguranca": to_utc(getattr(n, "data_seguranca", None)),
                    "data_criacao": to_utc(n.data_criacao),
                    "data_conclusao": to_utc(n.data_conclusao),
                    "pdf_path": n.pdf_path,
                    "pdf_carregado": bool(n.pdf_carregado),
                    "comentario_decisao": n.comentario_decisao,
                    "itens": itens,
                    "assinaturas": {p: _assinatura(n, p) for p in PAPEIS_ENTREGA},
                    "historico": historico,
                }
            )

        print(f"notas_entrega ...... {len(docs_notas_entrega)}  "
              f"(itens embutidos: {total_itens_e}, eventos de histórico: {total_hist_e})")
        if not dry_run and docs_notas_entrega:
            db.notas_entrega.insert_many(docs_notas_entrega)

        # -- counters ---------------------------------------------------
        # Mesma coleção/formato de app/repositories/counters.py:
        # _id="<tipo>_<ano>", campo "valor" (nao "seq").
        docs_cont = [
            {"_id": f"notas_saida_{ano}", "valor": seq}
            for ano, seq in contadores_saida.items()
        ] + [
            {"_id": f"notas_entrega_{ano}", "valor": seq}
            for ano, seq in contadores_entrega.items()
        ]
        print(f"counters ........... {len(docs_cont)}  "
              + ", ".join(f"{c['_id']}={c['valor']}" for c in docs_cont))
        if not dry_run and docs_cont:
            for c in docs_cont:
                db.counters.update_one({"_id": c["_id"]}, {"$set": c}, upsert=True)

    # -- índices + catálogo de módulos ------------------------------------
    if not dry_run:
        ensure_indexes()
        ModuloRepository(db).semear_catalogo()
        print("índices ............ garantidos")
        print("modulos ............ catálogo semeado")

    print("\n" + ("DRY-RUN: nada foi escrito." if dry_run else "Migração concluída."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migra SQLite -> MongoDB (Nota de Saída e Entrega).")
    parser.add_argument("--dry-run", action="store_true", help="simula, não escreve")
    parser.add_argument("--limpar", action="store_true", help="apaga as coleções alvo antes")
    args = parser.parse_args()
    migrar(dry_run=args.dry_run, limpar=args.limpar)
