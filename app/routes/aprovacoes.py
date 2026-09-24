"""Aprovação e rejeição de notas pendentes (Nota de Saída e Nota de Entrega)."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.nota import DecisaoForm
from app.models.nota import NotaSaida
from app.models.nota_entrega import NotaEntrega
from app.repositories.entrega import MongoEntregaRepository
from app.repositories.notas import MongoNotaRepository
from app.services import entrega_service, nota_service, notificacoes
from app.utils.assinatura import ler_posicao
from app.utils.constants import EstadoNota, Perfil
from app.utils.decorators import perfis_requeridos

bp = Blueprint("aprovacoes", __name__, url_prefix="/aprovacoes")

# Este blueprint é partilhado pelos dois módulos (Nota de Saída e Nota de
# Entrega) — quem decide (aprovar/rejeitar/devolver) precisa de saber a
# QUAL das duas tabelas o nota_id pertence, já que cada tipo tem a sua
# própria sequência de IDs independente (o mesmo número existe nos dois).
# Cada tipo pode estar em Mongo ou SQL, cada um pela sua própria flag.
_MODELOS = {"saida": NotaSaida, "entrega": NotaEntrega}
_SERVICOS = {"saida": nota_service, "entrega": entrega_service}
_BLUEPRINTS = {"saida": "notas", "entrega": "entrega"}
_MONGO_ATIVO = {"saida": nota_service._mongo_notas_ativo, "entrega": entrega_service._mongo_entrega_ativo}
_MONGO_REPOS = {"saida": MongoNotaRepository, "entrega": MongoEntregaRepository}


def _obter_nota(tipo, nota_id):
    if _MONGO_ATIVO[tipo]():
        return _MONGO_REPOS[tipo]().obter_por_id(nota_id)
    try:
        return db.session.get(_MODELOS[tipo], int(nota_id))
    except (TypeError, ValueError):
        return None


@bp.route("/")
@login_required
@perfis_requeridos(Perfil.APROVADOR.value)
def listar():
    if nota_service._mongo_notas_ativo():
        saidas = MongoNotaRepository().listar({"estado": EstadoNota.PENDENTE_APROVACAO.value})
    else:
        saidas = (
            NotaSaida.query.filter_by(estado=EstadoNota.PENDENTE_APROVACAO.value)
            .order_by(NotaSaida.data_criacao.asc())
            .all()
        )
    if entrega_service._mongo_entrega_ativo():
        entregas = MongoEntregaRepository().listar({"estado": EstadoNota.PENDENTE_APROVACAO.value})
    else:
        entregas = (
            NotaEntrega.query.filter_by(estado=EstadoNota.PENDENTE_APROVACAO.value)
            .order_by(NotaEntrega.data_criacao.asc())
            .all()
        )
    pendentes = [("saida", n) for n in saidas] + [("entrega", n) for n in entregas]
    pendentes.sort(key=lambda par: par[1].data_criacao)
    return render_template("aprovacoes/listar.html", pendentes=pendentes)


def _processar_devolver(tipo, servico, nota, form, comentario, voltar):
    if not comentario:
        flash("Indique o motivo da devolução para revisão.", "warning")
        return voltar()
    if not form.tecnico_revisao.data or form.tecnico_revisao.data == "0":
        flash("Seleccione o técnico que deve rever a nota.", "warning")
        return voltar()
    try:
        servico.devolver_para_revisao(nota, current_user, form.tecnico_revisao.data, comentario)
    except ValueError as erro:
        flash(str(erro), "warning")
        return voltar()
    notificacoes.nota_decidida(tipo, nota, "devolvida", current_user, comentario)
    flash("Nota devolvida para revisão ao técnico seleccionado.", "success")
    return voltar()


def _processar_rejeitar(tipo, servico, nota, comentario, voltar):
    if not comentario:
        flash("Indique o motivo da rejeição.", "warning")
        return voltar()
    servico.rejeitar_nota(nota, current_user, comentario)
    notificacoes.nota_decidida(tipo, nota, "rejeitada", current_user, comentario)
    flash("Nota rejeitada. O técnico poderá corrigir e resubmeter.", "info")
    return voltar()


def _processar_aprovar(tipo, servico, nota, comentario, voltar):
    servico.aprovar_nota(
        nota,
        current_user,
        comentario,
        posicao_assinatura=ler_posicao(request.form, papel="aprovador"),
    )
    notificacoes.nota_decidida(tipo, nota, "aprovada", current_user, comentario)
    flash(
        "Nota aprovada e assinada. Falta a assinatura de «Recebido» para concluir.",
        "success",
    )
    return voltar()


@bp.route("/<tipo>/<nota_id>/decidir", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.APROVADOR.value)
def decidir(tipo, nota_id):
    servico = _SERVICOS.get(tipo)
    blueprint = _BLUEPRINTS.get(tipo)
    if servico is None:
        abort(404)

    nota = _obter_nota(tipo, nota_id)
    if nota is None:
        abort(404)

    def _voltar():
        return redirect(url_for(f"{blueprint}.detalhe", nota_id=nota.id))

    if not nota.pode_aprovar(current_user):
        flash("Esta nota já não se encontra pendente de aprovação.", "warning")
        return _voltar()

    form = DecisaoForm()
    form.tecnico_revisao.choices = servico.choices_tecnicos()
    if not form.validate_on_submit():
        flash("Não foi possível processar a decisão.", "danger")
        return _voltar()

    comentario = (form.comentario.data or "").strip() or None
    if form.devolver.data:
        return _processar_devolver(tipo, servico, nota, form, comentario, _voltar)
    if form.rejeitar.data:
        return _processar_rejeitar(tipo, servico, nota, comentario, _voltar)
    return _processar_aprovar(tipo, servico, nota, comentario, _voltar)
