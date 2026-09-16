"""Seleção do módulo de trabalho após o login (Nota de Saída / Nota de Entrega)."""

from flask import Blueprint, redirect, render_template, session, url_for
from flask_login import current_user, login_required

bp = Blueprint("modulos", __name__)

# Cada módulo agrupa os blueprints que lhe pertencem. O guard em app/__init__.py
# usa este mapa para só deixar o utilizador entrar depois de escolher o módulo.
MODULOS = {
    "saida": {
        "nome": "Nota de Saída",
        "descricao": "Entrega de equipamento de TI a colaboradores, com fluxo de "
        "aprovação e assinatura digital.",
        "icone": "bi-box-arrow-right",
        # blueprints exclusivos deste módulo
        "blueprints": {"notas"},
        "disponivel": True,
    },
    "entrega": {
        "nome": "Nota de Entrega",
        "descricao": "Entrega de material a balcões e filiais, com o mesmo fluxo "
        "de aprovação e assinaturas — o Segurança assina por último.",
        "icone": "bi-truck",
        "blueprints": {"entrega"},
        "disponivel": True,
    },
}

# Blueprints partilhados por todos os módulos (aprovações e administração).
_BLUEPRINTS_PARTILHADOS = {"aprovacoes", "admin"}

# blueprint → conjunto de módulos que o podem usar.
BLUEPRINT_PARA_MODULO = {}
for _chave, _dados in MODULOS.items():
    for _bp in _dados["blueprints"]:
        BLUEPRINT_PARA_MODULO.setdefault(_bp, set()).add(_chave)
for _bp in _BLUEPRINTS_PARTILHADOS:
    BLUEPRINT_PARA_MODULO[_bp] = set(MODULOS)


def home_do_modulo(chave):
    """O Administrador gere a plataforma e não interage com notas — vai
    sempre para a área de utilizadores, independentemente do módulo escolhido.
    «Painel de Controlo» foi eliminado: os cards de resumo vivem agora no
    topo da listagem completa de cada módulo."""
    if current_user.is_admin():
        return url_for("admin.utilizadores")
    if chave == "entrega":
        return url_for("entrega.listar")
    return url_for("notas.listar")


@bp.route("/modulos")
@login_required
def escolher():
    # O Administrador não escolhe módulo — gere a plataforma diretamente,
    # num módulo único e implícito.
    if current_user.is_admin():
        return redirect(url_for("admin.utilizadores"))
    return render_template(
        "modulos/escolher.html",
        modulos=MODULOS,
        modulo_selecionado=session.get("modulo"),
    )


@bp.route("/modulos/<nome>")
@login_required
def entrar(nome):
    if current_user.is_admin():
        return redirect(url_for("admin.utilizadores"))
    if nome not in MODULOS or not MODULOS[nome]["disponivel"]:
        return redirect(url_for("modulos.escolher"))
    session["modulo"] = nome
    return redirect(home_do_modulo(nome))


@bp.route("/modulos/sair")
@login_required
def sair():
    """Volta ao ecrã de seleção, esquecendo o módulo ativo."""
    if current_user.is_admin():
        return redirect(url_for("admin.utilizadores"))
    session.pop("modulo", None)
    return redirect(url_for("modulos.escolher"))
