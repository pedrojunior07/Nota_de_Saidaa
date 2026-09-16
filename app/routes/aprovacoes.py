"""Aprovação e rejeição de notas pendentes."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.nota import DecisaoForm
from app.models.nota import NotaSaida
from app.services import nota_service
from app.utils.assinatura import ler_posicao
from app.utils.constants import EstadoNota, Perfil
from app.utils.decorators import perfis_requeridos

bp = Blueprint("aprovacoes", __name__, url_prefix="/aprovacoes")


@bp.route("/")
@login_required
@perfis_requeridos(Perfil.APROVADOR.value)
def listar():
    from app.models.nota_entrega import NotaEntrega

    saidas = (
        NotaSaida.query.filter_by(estado=EstadoNota.PENDENTE_APROVACAO.value)
        .order_by(NotaSaida.data_criacao.asc())
        .all()
    )
    entregas = (
        NotaEntrega.query.filter_by(estado=EstadoNota.PENDENTE_APROVACAO.value)
        .order_by(NotaEntrega.data_criacao.asc())
        .all()
    )
    pendentes = [("saida", n) for n in saidas] + [("entrega", n) for n in entregas]
    pendentes.sort(key=lambda par: par[1].data_criacao)
    return render_template("aprovacoes/listar.html", pendentes=pendentes)


@bp.route("/<int:nota_id>/decidir", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.APROVADOR.value)
def decidir(nota_id):
    nota = db.session.get(NotaSaida, nota_id)
    if nota is None:
        abort(404)
    if not nota.pode_aprovar(current_user):
        flash("Esta nota já não se encontra pendente de aprovação.", "warning")
        return redirect(url_for("notas.detalhe", nota_id=nota.id))

    form = DecisaoForm()
    form.tecnico_revisao.choices = nota_service.choices_tecnicos()
    if not form.validate_on_submit():
        flash("Não foi possível processar a decisão.", "danger")
        return redirect(url_for("notas.detalhe", nota_id=nota.id))

    comentario = (form.comentario.data or "").strip() or None
    if form.devolver.data:
        if not comentario:
            flash("Indique o motivo da devolução para revisão.", "warning")
            return redirect(url_for("notas.detalhe", nota_id=nota.id))
        if not form.tecnico_revisao.data:
            flash("Seleccione o técnico que deve rever a nota.", "warning")
            return redirect(url_for("notas.detalhe", nota_id=nota.id))
        try:
            nota_service.devolver_para_revisao(
                nota, current_user, form.tecnico_revisao.data, comentario
            )
        except ValueError as erro:
            flash(str(erro), "warning")
            return redirect(url_for("notas.detalhe", nota_id=nota.id))
        flash("Nota devolvida para revisão ao técnico seleccionado.", "success")
    elif form.rejeitar.data:
        if not comentario:
            flash("Indique o motivo da rejeição.", "warning")
            return redirect(url_for("notas.detalhe", nota_id=nota.id))
        nota_service.rejeitar_nota(nota, current_user, comentario)
        flash("Nota rejeitada. O técnico poderá corrigir e resubmeter.", "info")
    else:
        nota_service.aprovar_nota(
            nota,
            current_user,
            comentario,
            posicao_assinatura=ler_posicao(request.form, papel="aprovador"),
        )
        flash(
            "Nota aprovada e assinada. Falta a assinatura de «Recebido» para "
            "concluir.",
            "success",
        )
    return redirect(url_for("notas.detalhe", nota_id=nota.id))
