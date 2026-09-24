"""Mantém só um utilizador real (por omissão A272754, promovido a
Administrador) e apaga todos os outros utilizadores de exemplo/mockup —
incluindo as notas de demonstração que eles criaram (senão ficariam
"órfãs", sem autor válido).

Corre nos dois motores conforme as flags atuais do ambiente
(USE_MONGO_USERS/NOTAS/ENTREGA) — o mesmo sítio de onde a app está
realmente a ler/escrever agora.

Uso:
    python -m scripts.manter_apenas_utilizador --dry-run   # só mostra o que faria
    python -m scripts.manter_apenas_utilizador             # apaga a sério
    python -m scripts.manter_apenas_utilizador --manter A272754 --perfil administrador
"""

from __future__ import annotations

import argparse

from app import create_app
from app.utils.constants import Perfil


def _mongo_users_ativo() -> bool:
    from app.services.auth_service import _mongo_users_ativo as _flag

    return _flag()


def _mongo_notas_ativo() -> bool:
    from app.services.nota_service import _mongo_notas_ativo as _flag

    return _flag()


def _mongo_entrega_ativo() -> bool:
    from app.services.entrega_service import _mongo_entrega_ativo as _flag

    return _flag()


def limpar(manter_username: str, perfil_final: str, dry_run: bool = False) -> None:
    app = create_app()
    with app.app_context():
        manter_username = manter_username.strip().upper()

        # -- localizar todos os utilizadores, em SQL ou Mongo -----------
        if _mongo_users_ativo():
            from app.repositories.users import UserRepository

            repo_u = UserRepository()
            todos = repo_u.listar()
        else:
            from app.models.user import User

            todos = User.query.all()

        manter = next((u for u in todos if u.username == manter_username), None)
        if manter is None:
            print(f"ERRO: não encontrei nenhum utilizador com username '{manter_username}'. Nada feito.")
            return

        apagar = [u for u in todos if u.id != manter.id]
        print(f"A manter: {manter.username} ({manter.nome}) — perfil final: {perfil_final}")
        print(f"A apagar: {[f'{u.username} ({u.nome})' for u in apagar]}")

        # -- apagar as notas criadas pelos utilizadores a remover -------
        # (senão ficariam sem autor válido depois de o utilizador desaparecer)
        ids_apagar = {u.id for u in apagar}

        def _limpar_notas_saida():
            if _mongo_notas_ativo():
                from app.repositories.notas import MongoNotaRepository

                repo = MongoNotaRepository()
                notas = [n for n in repo.listar() if n.criado_por in ids_apagar]
                print(f"  notas_saida de exemplo a apagar: {len(notas)}")
                if not dry_run:
                    for n in notas:
                        repo.apagar(n.id)
            else:
                from app.extensions import db
                from app.models.nota import NotaSaida

                notas = NotaSaida.query.filter(NotaSaida.criado_por.in_(ids_apagar)).all()
                print(f"  notas_saida (SQL) de exemplo a apagar: {len(notas)}")
                if not dry_run:
                    for n in notas:
                        db.session.delete(n)
                    db.session.commit()

        def _limpar_notas_entrega():
            if _mongo_entrega_ativo():
                from app.repositories.entrega import MongoEntregaRepository

                repo = MongoEntregaRepository()
                notas = [n for n in repo.listar() if n.criado_por in ids_apagar]
                print(f"  notas_entrega de exemplo a apagar: {len(notas)}")
                if not dry_run:
                    for n in notas:
                        repo.apagar(n.id)
            else:
                from app.extensions import db
                from app.models.nota_entrega import NotaEntrega

                notas = NotaEntrega.query.filter(NotaEntrega.criado_por.in_(ids_apagar)).all()
                print(f"  notas_entrega (SQL) de exemplo a apagar: {len(notas)}")
                if not dry_run:
                    for n in notas:
                        db.session.delete(n)
                    db.session.commit()

        _limpar_notas_saida()
        _limpar_notas_entrega()

        # -- apagar os utilizadores em si --------------------------------
        if not dry_run:
            if _mongo_users_ativo():
                from app.repositories.users import UserRepository

                repo_u = UserRepository()
                for u in apagar:
                    repo_u.apagar(u.id)
                repo_u.atualizar(manter.id, {"perfil": perfil_final, "ativo": True})
            else:
                from app.extensions import db
                from app.models.user import User

                for u in apagar:
                    db.session.delete(u)
                manter_sql = db.session.get(User, manter.id)
                manter_sql.perfil = perfil_final
                manter_sql.ativo = True
                db.session.commit()
            print("\nConcluído: só o utilizador indicado ficou, com o perfil pedido.")
        else:
            print("\nDRY-RUN: nada foi apagado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mantém só um utilizador real, apaga o resto (utilizadores de exemplo + as suas notas).")
    parser.add_argument("--manter", default="A272754", help="username a manter (por omissão A272754)")
    parser.add_argument("--perfil", default=Perfil.ADMINISTRADOR.value, help="perfil final do utilizador mantido")
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que faria, não apaga nada")
    args = parser.parse_args()
    limpar(args.manter, args.perfil, dry_run=args.dry_run)
