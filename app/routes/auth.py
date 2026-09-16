"""Autenticação: login e logout."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app.forms.auth import LoginForm
from app.services.auth_service import autenticar

bp = Blueprint("auth", __name__)


def _destino_pos_login():
    """Após o login o utilizador escolhe o módulo; se já tiver um ativo, entra
    nele. O Administrador não escolhe módulo — gere a plataforma diretamente."""
    from app.routes.modulos import MODULOS, home_do_modulo

    if current_user.is_admin():
        session.setdefault("modulo", "saida")
        return url_for("admin.utilizadores")

    modulo = session.get("modulo")
    if modulo in MODULOS and MODULOS[modulo]["disponivel"]:
        return home_do_modulo(modulo)
    return url_for("modulos.escolher")


@bp.route("/")
def index():
    """Raiz do site: manda para o módulo ativo (ou para o login/escolha de
    módulo). Antes era a rota do «Painel de Controlo», entretanto eliminado."""
    if current_user.is_authenticated:
        return redirect(_destino_pos_login())
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_destino_pos_login())

    form = LoginForm()
    if form.validate_on_submit():
        utilizador = autenticar(form.username.data, form.password.data)
        if utilizador:
            login_user(utilizador, remember=form.lembrar.data)
            flash(f"Bem-vindo, {utilizador.nome}.", "success")
            return redirect(_destino_pos_login())
        flash("Credenciais inválidas ou conta sem acesso. Verifique o utilizador e/ou a" \
        " palavra-passe.", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
def logout():
    if current_user.is_authenticated:
        logout_user()
        flash("Sessão terminada com sucesso.", "info")
    session.pop("modulo", None)
    return redirect(url_for("auth.login"))
