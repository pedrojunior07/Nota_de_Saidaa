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
