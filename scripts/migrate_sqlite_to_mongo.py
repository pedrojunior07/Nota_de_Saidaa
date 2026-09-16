"""Migração única dos dados de SQLite (SQLAlchemy) para o MongoDB.

Lê a base relacional atual (instance/nota_saida.db, via create_app) e escreve as
coleções descritas em docs/Modelo_de_Dados_e_Backend.docx:

    users, modulos, contadores, notas_saida (com itens/assinaturas/historico
    embutidos), configuracao

Uso:
    python -m scripts.migrate_sqlite_to_mongo --dry-run   # só conta, não escreve
    python -m scripts.migrate_sqlite_to_mongo             # escreve (recusa se já houver dados)
    python -m scripts.migrate_sqlite_to_mongo --limpar    # apaga as coleções alvo e reescreve

Requer as variáveis MONGO_* no .env (ver .env.example).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app import create_app
from app.models.configuracao import Configuracao
from app.models.historico import Historico
from app.models.nota import NotaSaida
from app.models.user import User
from app.repositories.base import ensure_indexes, get_db
from app.repositories.modulos import ModuloRepository

MAPUTO = ZoneInfo("Africa/Maputo")
COLECOES_ALVO = ["users", "modulos", "contadores", "notas_saida", "configuracao"]


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
        return None
    return {
        "path": path,
        "x": getattr(nota, f"assinatura_{prefixo}_x", None),
        "y": getattr(nota, f"assinatura_{prefixo}_y", None),
        "w": getattr(nota, f"assinatura_{prefixo}_w", None),
        "h": getattr(nota, f"assinatura_{prefixo}_h", None),
    }


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
        notas = NotaSaida.query.order_by(NotaSaida.id).all()
        config = Configuracao.query.filter_by(id=1).first()

        # -- users ---------------------------------------------------------
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
                    "user_id": res.inserted_id,
                    "username": doc["username"],
                    "nome": doc["nome"],
                }
        elif dry_run:
            for old_id, doc in docs_users:
                ref_por_id[old_id] = {
                    "user_id": None,
                    "username": doc["username"],
                    "nome": doc["nome"],
                }

        def ref(user_id):
            return ref_por_id.get(user_id) if user_id else None

        # -- notas_saida --------------------------------------------------
        contadores: dict[int, int] = defaultdict(int)
        docs_notas = []
        total_itens = total_hist = 0
        for n in notas:
            ano = n.data_emissao.year if n.data_emissao else 2026
            contadores[ano] = max(contadores[ano], n.id)
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
                    "tipo_item": it.tipo_item,
                    "descricao": it.descricao,
                    "numero_serie": it.numero_serie,
                    "quantidade": it.quantidade,
                }
                for it in n.itens
            ]
            total_itens += len(itens)
            total_hist += len(historico)
            docs_notas.append(
                {
                    "ano": ano,
                    "numero_sequencial": n.id,
                    "numero_referencia": n.numero_referencia,
                    "numero_remedy": n.numero_remedy,
                    "data_emissao": to_utc(n.data_emissao),
                    "estado": n.estado,
                    "destinatario": {
                        "nome": n.funcionario,
                        "email": n.email_funcionario,
                        "departamento": n.departamento,
                    },
                    "motivo": n.motivo,
                    "observacao": n.observacao,
                    "origem": {
                        "local": n.origem_local,
                        "local_emissao": n.local_emissao,
                    },
                    "criado_por": ref(n.criado_por),
                    "aprovado_por": ref(n.aprovado_por),
                    "revisao_tecnico": ref(n.revisao_tecnico_id),
                    "datas": {
                        "criacao": to_utc(n.data_criacao),
                        "aprovacao": to_utc(n.data_aprovacao),
                        "conclusao": to_utc(n.data_conclusao),
                    },
                    "decisao": {"comentario": n.comentario_decisao},
                    "pdf_path": n.pdf_path,
                    "itens": itens,
                    "assinaturas": {
                        "entregue": _assinatura(n, "entregue"),
                        "recebido": _assinatura(n, "recebido"),
                        "seguranca": _assinatura(n, "seguranca"),
                        "aprovador": _assinatura(n, "aprovador"),
                    },
                    "historico": historico,
                }
            )

        print(f"notas_saida ........ {len(docs_notas)}  "
              f"(itens embutidos: {total_itens}, eventos de histórico: {total_hist})")
        if not dry_run and docs_notas:
            db.notas_saida.insert_many(docs_notas)

        # -- contadores -------------------------------------------------
        docs_cont = [
            {"_id": f"notas_saida:{ano}", "seq": seq} for ano, seq in contadores.items()
        ]
        print(f"contadores ......... {len(docs_cont)}  "
              + ", ".join(f"{c['_id']}={c['seq']}" for c in docs_cont))
        if not dry_run and docs_cont:
            for c in docs_cont:
                db.contadores.update_one({"_id": c["_id"]}, {"$set": c}, upsert=True)

        # -- configuracao ---------------------------------------------
        if config is not None:
            doc_cfg = {
                "_id": "instituicao",
                "nome_instituicao": config.nome_instituicao,
                "direcao": config.direcao,
                "morada": config.morada,
                "contacto": config.contacto,
                "email_contacto": config.email_contacto,
                "rodape_pdf": config.rodape_pdf,
                "origem_de": config.origem_de,
                "origem_local": config.origem_local,
                "local_emissao": config.local_emissao,
            }
            print("configuracao ....... 1  (_id=instituicao)")
            if not dry_run:
                db.configuracao.replace_one({"_id": "instituicao"}, doc_cfg, upsert=True)
        else:
            print("configuracao ....... 0  (sem linha id=1 no SQLite)")

    # -- modulos + índices ----------------------------------------------
    if not dry_run:
        ModuloRepository(db).semear_catalogo()
        ensure_indexes()
        print("modulos ............ catálogo semeado; índices garantidos")

    print("\n" + ("DRY-RUN: nada foi escrito." if dry_run else "Migração concluída."))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migra SQLite -> MongoDB (Nota de Saída).")
    parser.add_argument("--dry-run", action="store_true", help="simula, não escreve")
    parser.add_argument("--limpar", action="store_true", help="apaga as coleções alvo antes")
    args = parser.parse_args()
    migrar(dry_run=args.dry_run, limpar=args.limpar)
