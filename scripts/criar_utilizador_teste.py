"""Cria (ou atualiza) um utilizador de TESTE com palavra-passe local.

Uso, na pasta do projeto (com o .venv ativo e a base de dados ligada):

    python scripts/criar_utilizador_teste.py A272755 "1234@"
    python scripts/criar_utilizador_teste.py A272755 "1234@" tecnico

A palavra-passe local só é usada com AUTH_MODE=local (no .env). Com
AUTH_MODE=api o login é validado no AD e esta palavra-passe é ignorada.
Só para testes locais — não usar em produção.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

from run import app  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    username, password = sys.argv[1].strip().upper(), sys.argv[2]
    perfil = (sys.argv[3] if len(sys.argv) > 3 else "administrador").strip().lower()

    with app.app_context():
        from app.repositories.users import UserRepository
        from app.services.auth_service import _mongo_users_ativo

        if _mongo_users_ativo():
            repo = UserRepository()
            u = repo.get_by_username(username)
            if u is None:
                repo.criar(username=username, perfil=perfil, password=password, nome="Utilizador de Teste")
                acao = "criado"
            else:
                repo.atualizar(u.id, {"perfil": perfil, "ativo": True,
                                      "password_hash": generate_password_hash(password)})
                acao = "atualizado"
            onde = "MongoDB"
        else:
            from app.extensions import db
            from app.models.user import User

            u = User.query.filter_by(username=username).first()
            acao = "atualizado"
            if u is None:
                u = User(username=username, nome="Utilizador de Teste")
                db.session.add(u)
                acao = "criado"
            u.perfil, u.ativo = perfil, True
            u.definir_password(password)
            db.session.commit()
            onde = "SQLite"

        modo = (app.config.get("AUTH_MODE") or "local").lower()
        print(f"OK: {username} {acao} ({onde}) com perfil '{perfil}'.")
        if modo != "local":
            print(f"ATENÇÃO: AUTH_MODE={modo}. Para entrar com esta palavra-passe, "
                  "ponha AUTH_MODE=local no .env e reinicie o flask run.")


if __name__ == "__main__":
    main()
