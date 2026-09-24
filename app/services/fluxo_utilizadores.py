"""Utilizadores que participam no fluxo das notas (técnicos e aprovadores).

Um só sítio para as listas dos dropdowns e para validar a escolha, em SQLite
e em MongoDB (USE_MONGO_USERS). Antes, a Nota de Saída só consultava o SQL —
em produção (utilizadores no Mongo) o dropdown de técnicos ficava vazio.
"""

from __future__ import annotations

from app.utils.constants import Perfil

PERFIS_TECNICO = {Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value}
PERFIS_APROVADOR = {Perfil.APROVADOR.value}


def _mongo_users() -> bool:
    from app.services.auth_service import _mongo_users_ativo

    return _mongo_users_ativo()


def listar_ativos(perfis: set[str]) -> list:
    if _mongo_users():
        from app.repositories.users import UserRepository

        utilizadores = [u for u in UserRepository().listar() if u.ativo and u.perfil in perfis]
    else:
        from app.models.user import User

        utilizadores = User.query.filter(User.ativo.is_(True), User.perfil.in_(list(perfis))).all()
    return sorted(utilizadores, key=lambda u: (u.nome_exibicao or "").lower())


def obter(user_id):
    if user_id in (None, "", "0", 0):
        return None
    if _mongo_users():
        from app.repositories.users import UserRepository

        return UserRepository().get(user_id)
    from app.extensions import db
    from app.models.user import User

    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def obter_valido(user_id, perfis: set[str], erro: str):
    utilizador = obter(user_id)
    if utilizador is None or not utilizador.ativo or utilizador.perfil not in perfis:
        raise ValueError(erro)
    return utilizador


def _choices(perfis: set[str], vazio: str) -> list[tuple[str, str]]:
    return [("0", vazio)] + [
        (str(u.id), f"{u.nome_exibicao} — {u.username}") for u in listar_ativos(perfis)
    ]


def choices_tecnicos() -> list[tuple[str, str]]:
    return _choices(PERFIS_TECNICO, "Seleccione o técnico")


def choices_aprovadores() -> list[tuple[str, str]]:
    return _choices(PERFIS_APROVADOR, "Seleccione o aprovador")


def obter_tecnico_valido(user_id):
    return obter_valido(user_id, PERFIS_TECNICO, "Seleccione um técnico de informática válido.")


def obter_aprovador_valido(user_id):
    return obter_valido(user_id, PERFIS_APROVADOR, "Seleccione o aprovador a quem enviar a nota.")
