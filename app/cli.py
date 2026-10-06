"""Comandos de linha de comandos da aplicação (flask <comando>).

    flask --app run definir-perfil A272754 administrador

Serve para repor o acesso quando a plataforma fica sem administrador (por
exemplo, se o único admin mudar o próprio perfil). Corre dentro do container
com a mesma ligação à base de dados da aplicação (MongoDB ou SQLite).
"""

from __future__ import annotations

import click
from flask import Flask

from app.utils.constants import PERFIS_LABEL


def registar_comandos(app: Flask) -> None:
    _registar_reset(app)

    @app.cli.command("definir-perfil")
    @click.argument("username")
    @click.argument("perfil")
    def definir_perfil(username: str, perfil: str) -> None:
        """Muda o perfil de um utilizador existente (e ativa-o)."""
        from app.services.auth_service import _mongo_users_ativo
        from app.repositories.users import normalizar_username

        perfil = perfil.strip().lower()
        if perfil not in PERFIS_LABEL:
            raise click.ClickException(
                f"Perfil inválido: {perfil}. Use um de: {', '.join(PERFIS_LABEL)}")
        username = normalizar_username(username)

        if _mongo_users_ativo():
            from app.repositories.users import UserRepository

            repo = UserRepository()
            utilizador = repo.get_by_username(username)
            if utilizador is None:
                raise click.ClickException(f"Utilizador {username} não existe (MongoDB).")
            repo.atualizar(utilizador.id, {"perfil": perfil, "ativo": True})
        else:
            from app.extensions import db
            from app.models.user import User

            utilizador = User.query.filter_by(username=username).first()
            if utilizador is None:
                raise click.ClickException(f"Utilizador {username} não existe (SQLite).")
            utilizador.perfil = perfil
            utilizador.ativo = True
            db.session.commit()
        click.echo(f"OK: {username} tem agora o perfil '{perfil}' ({PERFIS_LABEL[perfil]}).")


# ---------------------------------------------------------------------------
# reset-dados: limpa dados de teste, mantendo os utilizadores indicados
# ---------------------------------------------------------------------------
def _registar_reset(app: Flask) -> None:
    @app.cli.command("reset-dados")
    @click.option("--manter", default="A272754,C974468", show_default=True,
                  help="Nºs de colaborador a manter, separados por vírgula.")
    @click.option("--admin", default="A272754", show_default=True,
                  help="Utilizador que fica (ou passa a) Administrador ativo.")
    @click.option("--confirmar", is_flag=True,
                  help="Apaga a sério. Sem esta opção só mostra o que faria (simulação).")
    def reset_dados(manter: str, admin: str, confirmar: bool) -> None:
        """Apaga notas (saída e entrega), histórico, numeração, PDFs, assinaturas
        das notas e utilizadores de teste. Mantém configurações, módulos, campos
        dinâmicos, os utilizadores indicados e as suas assinaturas pessoais.
        Antes de apagar, guarda uma cópia em instance/backups/reset-<data>/."""
        import os
        import shutil
        from datetime import datetime

        from flask import current_app

        from app.repositories.users import normalizar_username
        from app.services.auth_service import _mongo_users_ativo
        from app.utils.constants import Perfil

        manter_set = {normalizar_username(u) for u in manter.split(",") if u.strip()}
        admin = normalizar_username(admin)
        manter_set.add(admin)
        flag = lambda n: os.environ.get(n, "0").strip().lower() in {"1", "true", "yes", "on"}
        mongo_users, mongo_notas, mongo_entrega = _mongo_users_ativo(), flag("USE_MONGO_NOTAS"), flag("USE_MONGO_ENTREGA")
        modo = "A APAGAR" if confirmar else "SIMULAÇÃO (nada é apagado)"
        click.echo(f"== reset-dados: {modo}")
        click.echo(f"   manter: {', '.join(sorted(manter_set))} | admin: {admin}")

        backup_dir = os.path.join(current_app.instance_path, "backups",
                                  "reset-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        if confirmar:
            os.makedirs(backup_dir, exist_ok=True)
            click.echo(f"   cópia de segurança em: {backup_dir}")

        # ---------------- MongoDB ----------------
        if mongo_users or mongo_notas or mongo_entrega:
            from bson import json_util

            from app.repositories.base import get_db

            mdb = get_db()

            def limpar(colecao, filtro):
                docs = list(mdb[colecao].find(filtro))
                click.echo(f"   Mongo {colecao}: {len(docs)} a apagar")
                if confirmar and docs:
                    with open(os.path.join(backup_dir, f"mongo_{colecao}.json"), "w", encoding="utf-8") as fh:
                        fh.write(json_util.dumps(docs, ensure_ascii=False))
                    mdb[colecao].delete_many({"_id": {"$in": [d["_id"] for d in docs]}})

            if mongo_notas:
                limpar("notas_saida", {})
            if mongo_entrega:
                limpar("notas_entrega", {})
            if mongo_notas or mongo_entrega:
                limpar("counters", {})
            if mongo_users:
                limpar("users", {"username": {"$nin": sorted(manter_set)}})

        # ---------------- SQLite / SQL ----------------
        from app.extensions import db
        from app.models.campo_dinamico import ValorCampoDinamico
        from app.models.historico import Historico
        from app.models.historico_entrega import HistoricoEntrega
        from app.models.item import ItemNota
        from app.models.item_entrega import ItemEntrega
        from app.models.nota import NotaSaida
        from app.models.nota_entrega import NotaEntrega
        from app.models.user import User

        uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if confirmar and uri.startswith("sqlite:///"):
            caminho = uri.replace("sqlite:///", "", 1)
            if os.path.isfile(caminho):
                shutil.copy2(caminho, os.path.join(backup_dir, os.path.basename(caminho)))
        consultas = [("valores de campos dinâmicos", ValorCampoDinamico.query),
                     ("histórico (saída)", Historico.query), ("histórico (entrega)", HistoricoEntrega.query),
                     ("itens (saída)", ItemNota.query), ("itens (entrega)", ItemEntrega.query),
                     ("notas de saída (SQL)", NotaSaida.query), ("notas de entrega (SQL)", NotaEntrega.query)]
        if not mongo_users:
            consultas.append(("utilizadores (SQL)", User.query.filter(~User.username.in_(sorted(manter_set)))))
        try:
            for nome, q in consultas:
                total = q.count()
                click.echo(f"   SQL {nome}: {total} a apagar")
                if confirmar and total:
                    q.delete(synchronize_session=False)
            if confirmar:
                db.session.commit()
        except Exception as erro:  # noqa: BLE001 — tabela inexistente numa BD antiga, etc.
            db.session.rollback()
            click.echo(f"   SQL: ignorado ({erro.__class__.__name__}: {erro})")

        # ---------------- Ficheiros (PDFs e assinaturas das notas) ----------------
        ids_mantidos = set()
        if mongo_users:
            from app.repositories.users import UserRepository

            repo = UserRepository()
            ids_mantidos = {str(u.id) for u in (repo.get_by_username(n) for n in manter_set) if u}
        else:
            ids_mantidos = {str(u.id) for u in User.query.filter(User.username.in_(sorted(manter_set)))}
        pessoais = {f"sig_user_{i}.png" for i in ids_mantidos}
        for chave, rotulo in (("PDF_FOLDER", "PDFs"), ("SIGNATURE_FOLDER", "assinaturas")):
            pasta = current_app.config.get(chave)
            if not pasta or not os.path.isdir(pasta):
                continue
            ficheiros = [f for f in os.listdir(pasta) if os.path.isfile(os.path.join(pasta, f)) and f not in pessoais]
            click.echo(f"   ficheiros {rotulo}: {len(ficheiros)} a apagar"
                       + (f" (mantidas {len(pessoais & set(os.listdir(pasta)))} assinaturas pessoais)" if rotulo == "assinaturas" else ""))
            if confirmar and ficheiros:
                destino = os.path.join(backup_dir, rotulo)
                os.makedirs(destino, exist_ok=True)
                for f in ficheiros:
                    shutil.move(os.path.join(pasta, f), os.path.join(destino, f))

        # ---------------- Garantir o administrador ----------------
        if confirmar:
            if mongo_users:
                from app.repositories.users import UserRepository

                repo = UserRepository()
                u = repo.get_by_username(admin)
                if u is None:
                    repo.criar(username=admin, perfil=Perfil.ADMINISTRADOR.value)
                else:
                    repo.atualizar(u.id, {"perfil": Perfil.ADMINISTRADOR.value, "ativo": True})
            else:
                u = User.query.filter_by(username=admin).first()
                if u is None:
                    db.session.add(User(username=admin, perfil=Perfil.ADMINISTRADOR.value, ativo=True))
                else:
                    u.perfil, u.ativo = Perfil.ADMINISTRADOR.value, True
                db.session.commit()
            click.echo(f"OK: dados limpos. {admin} é Administrador ativo.")
        else:
            click.echo("Simulação concluída. Para apagar a sério, repetir com --confirmar.")
