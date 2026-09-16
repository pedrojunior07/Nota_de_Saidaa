"""Decoradores de autorização por perfil."""

from functools import wraps

from flask import abort
from flask_login import current_user


def perfis_requeridos(*perfis):
    """Restringe o acesso a um ou mais perfis de utilizador."""

    def decorator(funcao):
        @wraps(funcao)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.perfil not in perfis:
                abort(403)
            return funcao(*args, **kwargs)

        return wrapper

    return decorator
