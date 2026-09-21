"""Fluxo da Nota de Entrega (modelo próprio, mesma lógica da Nota de Saída)."""

import os
from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import false, or_
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.forms.nota import CarregarNotaForm, DecisaoForm, NotaForm
from app.models.configuracao import Configuracao
from app.models.historico_entrega import HistoricoEntrega
from app.models.nota_entrega import NotaEntrega
from app.repositories.entrega import MongoEntregaRepository
from app.services import campos_dinamicos_service, entrega_service
from app.utils.assinatura import (
    guardar_dataurl_png,
    guardar_png,
    ler_posicao,
    nome_ficheiro,
    url_assinatura,
)
from app.utils.constants import ESTADOS_LABEL, TIPOS_ITEM, TIPOS_ITEM_COM_SAP, EstadoNota, Perfil
from app.utils.decorators import perfis_requeridos

bp = Blueprint("entrega", __name__, url_prefix="/entrega")


def _voltar_a_listar():
    return _voltar_a_listar()


@bp.before_request
def _bloquear_admin():
    """O Administrador gere a plataforma (utilizadores, permissões, campos) e
    não cria nem vê notas — isso é exclusivo do Técnico (e do Aprovador, só
    para decidir)."""
    if current_user.is_authenticated and current_user.is_admin():
        flash("Administradores gerem a plataforma e não têm acesso às notas.", "info")
        return redirect(url_for("admin.utilizadores"))


def _posicao(papel):
    return ler_posicao(request.form, papel=papel, tipo="entrega")


def _consulta_listagem():
    """Filtro «quem pode ver o quê», na forma certa para o backend ativo:
    uma Query SQLAlchemy normalmente, ou um dict de filtro Mongo quando
    USE_MONGO_ENTREGA está ligado."""
    if entrega_service._mongo_entrega_ativo():
        if current_user.perfil == Perfil.APROVADOR.value:
            return {"estado": {"$ne": EstadoNota.RASCUNHO.value}}
        if current_user.is_tecnico():
            return {"$or": [{"criado_por": current_user.id}, {"revisao_tecnico_id": current_user.id}]}
        return {"_id": None}

    if current_user.perfil == Perfil.APROVADOR.value:
        # O aprovador só decide/acompanha notas já submetidas — nunca vê
        # rascunhos que o técnico ainda nem entregou para revisão.
        return NotaEntrega.query.filter(NotaEntrega.estado != EstadoNota.RASCUNHO.value)
    if current_user.is_tecnico():
        return NotaEntrega.query.filter(
            or_(
                NotaEntrega.criado_por == current_user.id,
                NotaEntrega.revisao_tecnico_id == current_user.id,
            )
        )
    return NotaEntrega.query.filter(false())


def _obter_ou_404(nota_id):
    if entrega_service._mongo_entrega_ativo():
        nota = MongoEntregaRepository().obter_por_id(nota_id)
    else:
        try:
            nota = db.session.get(NotaEntrega, int(nota_id))
        except (TypeError, ValueError):
            nota = None
    if nota is None:
        abort(404)
    return nota


def _pode_ver(nota):
    if current_user.is_aprovador():
        return nota.estado != EstadoNota.RASCUNHO.value
    return current_user.is_tecnico() and (
        nota.criado_por == current_user.id or nota.revisao_tecnico_id == current_user.id
    )


def _itens_do_pedido():
    itens = entrega_service.extrair_itens(request.form)
    return itens or [_item_vazio()]


def _item_vazio():
    return {
        "tipo_item": "",
        "destino": "",
        "descricao": "",
        "numero_serie": "",
        "numero_sap": "",
        "quantidade": 1,
    }


def _ler_respostas_campos(campos):
    """Lê do POST os valores da secção «Campos adicionais» (nome dos inputs:
    ``campo_<id>``)."""
    return {campo.id: request.form.get(f"campo_{campo.id}") for campo in campos}


# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
def painel():
    """«Painel de Controlo» foi eliminado — os cards de resumo agora vivem no
    topo da listagem completa. Mantido como redireccionamento por compatibilidade."""
    return _voltar_a_listar()


@bp.route("/listar")
@login_required
def listar():
    pagina = request.args.get("pagina", 1, type=int)
    referencia = request.args.get("referencia", "").strip()
    colaborador = request.args.get("colaborador", "").strip()
    estado = request.args.get("estado", "").strip()
    data_inicio = request.args.get("data_inicio") or None
    data_fim = request.args.get("data_fim") or None
    di = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else None
    df = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else None

    if entrega_service._mongo_entrega_ativo():
        from app.utils.pagination import SimplePagination

        encontradas = entrega_service.pesquisar_mongo(
            _consulta_listagem(),
            referencia=referencia or None,
            colaborador=colaborador or None,
            estado=estado or None,
            data_inicio=di,
            data_fim=df,
        )
        paginacao = SimplePagination(encontradas, pagina, current_app.config["ITEMS_PER_PAGE"])
        stats = entrega_service.estatisticas_mongo(_consulta_listagem())
    else:
        consulta = entrega_service.pesquisar(
            _consulta_listagem(),
            referencia=referencia or None,
            colaborador=colaborador or None,
            estado=estado or None,
            data_inicio=di,
            data_fim=df,
        )
        paginacao = consulta.paginate(
            page=pagina, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False
        )
        stats = entrega_service.estatisticas(_consulta_listagem())
    return render_template(
        "entrega/listar.html",
        paginacao=paginacao,
        estados=ESTADOS_LABEL,
        stats=stats,
        form_carregar=CarregarNotaForm(),
        filtros={
            "referencia": referencia,
            "colaborador": colaborador,
            "estado": estado,
            "data_inicio": data_inicio or "",
            "data_fim": data_fim or "",
        },
    )


@bp.route("/carregar", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value)
def carregar():
    """Regista na base de dados uma Nota de Entrega já existente (PDF externo),
    sem passar pelo formulário completo de criação."""
    form = CarregarNotaForm()
    if not form.validate_on_submit():
        primeiro_erro = next(iter(form.errors.values()), [None])[0]
        flash(primeiro_erro or "Não foi possível carregar a nota. Verifique os dados.", "danger")
        return _voltar_a_listar()

    ficheiro = request.files.get(form.ficheiro.name)
    try:
        nota = entrega_service.carregar_nota(form.data, ficheiro, current_user)
    except ValueError as erro:
        flash(str(erro), "warning")
        return _voltar_a_listar()
    except (IntegrityError, DuplicateKeyError):
        db.session.rollback()
        flash("Já existe uma nota com este número de referência Remedy.", "danger")
        return _voltar_a_listar()

    flash("Nota carregada e adicionada à listagem.", "success")
    return redirect(url_for("entrega.detalhe", nota_id=nota.id))


@bp.route("/nova", methods=["GET", "POST"])
@login_required
@perfis_requeridos(Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value)
def criar():
    form = NotaForm()
    if request.method == "GET":
        form.data_emissao.data = date.today()
        config = Configuracao.obter()
        form.origem_local.data = config.origem_local or "Sede IT"
        form.local_emissao.data = config.local_emissao or "Maputo"
    itens_form = _itens_do_pedido() if request.method == "POST" else [_item_vazio()]
    campos_extra = campos_dinamicos_service.listar_aplicaveis("entrega")
    valores_extra = _ler_respostas_campos(campos_extra) if request.method == "POST" else {}

    if request.method == "POST" and form.validate():
        itens = entrega_service.extrair_itens(request.form)
        faltam = campos_dinamicos_service.validar_obrigatorios("entrega", valores_extra)
        if not itens:
            flash("Adicione pelo menos um item.", "warning")
        elif faltam:
            flash("Preencha os campos obrigatórios: " + ", ".join(faltam) + ".", "warning")
        elif form.submeter.data and not current_user.assinatura_path:
            flash("Carregue a sua assinatura PNG reutilizável antes de confirmar.", "warning")
        else:
            try:
                pediu_submeter = bool(form.submeter.data)
                form.motivo.data = form.motivo_efetivo()
                nota = entrega_service.criar_nota(
                    form.data, itens, current_user, posicao_assinatura=_posicao("entregue")
                )
                campos_dinamicos_service.guardar_valores("entrega", nota.id, valores_extra)
                if pediu_submeter:
                    flash(
                        "Rascunho criado. Recolha a assinatura «Entregue Por» "
                        "abaixo para submeter.",
                        "info",
                    )
                else:
                    flash("Rascunho guardado com sucesso.", "success")
                return redirect(url_for("entrega.detalhe", nota_id=nota.id))
            except (IntegrityError, DuplicateKeyError):
                db.session.rollback()
                flash("Já existe uma nota de entrega com este número Remedy.", "danger")

    return render_template(
        "entrega/formulario.html",
        form=form,
        itens=itens_form,
        tipos_item=TIPOS_ITEM,
        tipos_item_sap=TIPOS_ITEM_COM_SAP,
        campos_extra=campos_extra,
        valores_extra=valores_extra,
        titulo="Nova Nota de Entrega",
    )


@bp.route("/<nota_id>/editar", methods=["GET", "POST"])
@login_required
def editar(nota_id):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_editar(current_user):
        abort(403)

    form = NotaForm(obj=nota)
    form.garantir_motivo(nota.motivo)
    itens_form = (
        _itens_do_pedido()
        if request.method == "POST"
        else [
            {
                "tipo_item": i.tipo_item,
                "destino": i.destino or "",
                "descricao": i.descricao,
                "numero_serie": i.numero_serie or "",
                "numero_sap": i.numero_sap or "",
                "quantidade": i.quantidade,
            }
            for i in nota.itens
        ]
        or [_item_vazio()]
    )
    campos_extra = campos_dinamicos_service.listar_aplicaveis("entrega")
    valores_extra = (
        _ler_respostas_campos(campos_extra)
        if request.method == "POST"
        else campos_dinamicos_service.obter_valores("entrega", nota.id)
    )

    if request.method == "POST" and form.validate():
        itens = entrega_service.extrair_itens(request.form)
        faltam = campos_dinamicos_service.validar_obrigatorios("entrega", valores_extra)
        if not itens:
            flash("Adicione pelo menos um item.", "warning")
        elif faltam:
            flash("Preencha os campos obrigatórios: " + ", ".join(faltam) + ".", "warning")
        else:
            try:
                pediu_submeter = bool(form.submeter.data)
                submeter = pediu_submeter and nota.assinaturas_entrega_ok
                form.motivo.data = form.motivo_efetivo()
                entrega_service.atualizar_nota(
                    nota, form.data, itens, current_user,
                    submeter=submeter, posicao_assinatura=_posicao("entregue"),
                )
                campos_dinamicos_service.guardar_valores("entrega", nota.id, valores_extra)
                if submeter:
                    flash("Nota submetida para aprovação.", "success")
                elif pediu_submeter:
                    flash(
                        "Nota guardada. Recolha a assinatura «Entregue Por» "
                        "para submeter.",
                        "info",
                    )
                else:
                    flash("Nota atualizada.", "success")
                return redirect(url_for("entrega.detalhe", nota_id=nota.id))
            except (IntegrityError, DuplicateKeyError):
                db.session.rollback()
                flash("Já existe uma nota de entrega com este número Remedy.", "danger")

    return render_template(
        "entrega/formulario.html",
        form=form,
        itens=itens_form,
        tipos_item=TIPOS_ITEM,
        tipos_item_sap=TIPOS_ITEM_COM_SAP,
        campos_extra=campos_extra,
        valores_extra=valores_extra,
        titulo=f"Editar Nota de Entrega {nota.numero_referencia}",
        nota=nota,
    )


@bp.route("/<nota_id>")
@login_required
def detalhe(nota_id):
    nota = _obter_ou_404(nota_id)
    if not _pode_ver(nota):
        abort(403)
    historico = (
        HistoricoEntrega.query.filter_by(nota_id=nota.id)
        .order_by(HistoricoEntrega.data_hora.desc())
        .all()
    )
    form_decisao = DecisaoForm()
    form_decisao.tecnico_revisao.choices = entrega_service.choices_tecnicos()
    form_decisao.tecnico_revisao.data = nota.revisao_tecnico_id or nota.criado_por
    return render_template(
        "entrega/detalhe.html",
        nota=nota,
        historico=historico,
        form_decisao=form_decisao,
        campos_valores=campos_dinamicos_service.valores_para_exibir("entrega", nota.id),
    )


@bp.route("/<nota_id>/submeter", methods=["POST"])
@login_required
def submeter(nota_id):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        abort(403)
    if not nota.itens:
        flash("Não é possível submeter uma nota sem itens.", "warning")
        return redirect(url_for("entrega.detalhe", nota_id=nota.id))
    try:
        entrega_service.submeter_nota(nota, current_user)
    except ValueError as erro:
        db.session.rollback()
        flash(str(erro), "warning")
        return redirect(url_for("entrega.detalhe", nota_id=nota.id))
    flash("Nota submetida para aprovação.", "success")
    return redirect(url_for("entrega.detalhe", nota_id=nota.id))


@bp.route("/<nota_id>/decidir", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.APROVADOR.value)
def decidir(nota_id):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_aprovar(current_user):
        flash("Esta nota já não se encontra pendente de aprovação.", "warning")
        return redirect(url_for("entrega.detalhe", nota_id=nota.id))

    form = DecisaoForm()
    form.tecnico_revisao.choices = entrega_service.choices_tecnicos()
    if not form.validate_on_submit():
        flash("Não foi possível processar a decisão.", "danger")
        return redirect(url_for("entrega.detalhe", nota_id=nota.id))

    comentario = (form.comentario.data or "").strip() or None
    if form.devolver.data:
        if not comentario or not form.tecnico_revisao.data:
            flash("Indique o motivo e o técnico para a devolução.", "warning")
            return redirect(url_for("entrega.detalhe", nota_id=nota.id))
        try:
            entrega_service.devolver_para_revisao(
                nota, current_user, form.tecnico_revisao.data, comentario
            )
        except ValueError as erro:
            flash(str(erro), "warning")
            return redirect(url_for("entrega.detalhe", nota_id=nota.id))
        flash("Nota devolvida para revisão.", "success")
    elif form.rejeitar.data:
        if not comentario:
            flash("Indique o motivo da rejeição.", "warning")
            return redirect(url_for("entrega.detalhe", nota_id=nota.id))
        entrega_service.rejeitar_nota(nota, current_user, comentario)
        flash("Nota rejeitada.", "info")
    else:
        entrega_service.aprovar_nota(
            nota, current_user, comentario, posicao_assinatura=_posicao("aprovador")
        )
        flash(
            "Nota aprovada e assinada. Falta a assinatura de «Recebido» para "
            "concluir. A do Segurança é opcional.",
            "success",
        )
    return redirect(url_for("entrega.detalhe", nota_id=nota.id))


@bp.route("/<nota_id>/assinatura/<papel>", methods=["POST"])
@login_required
def guardar_assinatura(nota_id, papel):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        return jsonify({"error": "Sem permissão para recolher assinaturas."}), 403
    dados = request.get_json(silent=True) or {}
    try:
        fname = entrega_service.guardar_assinatura_papel(
            nota, papel, dados.get("imagem"), current_user, posicao=dados.get("posicao")
        )
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    return jsonify({"ok": True, "url": url_assinatura(fname), "estado": nota.estado})


@bp.route("/<nota_id>/assinatura/<papel>/remover", methods=["POST"])
@login_required
def remover_assinatura(nota_id, papel):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        return jsonify({"error": "Sem permissão."}), 403
    try:
        entrega_service.remover_assinatura_papel(nota, papel, current_user)
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    return jsonify({"ok": True})


@bp.route("/<nota_id>/assinatura/<papel>/posicao", methods=["POST"])
@login_required
def atualizar_posicao_assinatura(nota_id, papel):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        return jsonify({"error": "Sem permissão."}), 403
    dados = request.get_json(silent=True) or {}
    try:
        entrega_service.atualizar_posicao_assinatura(
            nota, papel, dados.get("posicao"), current_user
        )
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    return jsonify({"ok": True})


@bp.route("/<nota_id>/apagar", methods=["POST"])
@login_required
def apagar(nota_id):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_editar(current_user):
        abort(403)
    entrega_service.apagar_nota(nota)
    flash("Nota apagada com sucesso.", "success")
    return _voltar_a_listar()


@bp.route("/<nota_id>/pdf")
@login_required
def pdf(nota_id):
    nota = _obter_ou_404(nota_id)
    if not _pode_ver(nota):
        abort(403)
    if nota.pdf_carregado:
        # Nota registada a partir de um PDF externo: nunca regenerar, servir
        # exatamente o ficheiro que foi carregado.
        if not nota.pdf_path or not os.path.isfile(nota.pdf_path):
            abort(404)
        caminho = nota.pdf_path
    else:
        if nota.estado != EstadoNota.CONCLUIDA.value:
            flash("O PDF fica disponível quando a nota estiver concluída.", "warning")
            return redirect(url_for("entrega.detalhe", nota_id=nota.id))
        caminho = entrega_service.garantir_pdf(nota)
    inline = request.args.get("inline") == "1"
    return send_file(
        caminho,
        as_attachment=not inline,
        download_name=f"Nota_Entrega_{nota.numero_documento.replace('/', '-')}.pdf",
        mimetype="application/pdf",
    )


@bp.route("/assinaturas/<path:filename>")
@login_required
def servir_assinatura(filename):
    nome = nome_ficheiro(filename)
    if not nome:
        abort(404)
    return send_from_directory(current_app.config["SIGNATURE_FOLDER"], nome)


def _obter_nota_para_auto_assinatura(nota_id):
    if entrega_service._mongo_entrega_ativo():
        return MongoEntregaRepository().obter_por_id(nota_id)
    try:
        return db.session.get(NotaEntrega, int(nota_id))
    except (TypeError, ValueError):
        return None


def _definir_assinatura_auto(nota_id, fname):
    """Ao guardar/apagar a assinatura reutilizável, aplica o mesmo path (ou
    limpa, se fname for None) no papel certo (aprovador/entregue) da nota
    indicada — só se o utilizador tiver permissão para esse papel."""
    if not nota_id:
        return
    nota = _obter_nota_para_auto_assinatura(nota_id)
    if not nota:
        return
    if nota.pode_aprovar(current_user):
        papel = "aprovador"
    elif nota.pode_editar(current_user):
        papel = "entregue"
    else:
        return
    if entrega_service._mongo_entrega_ativo():
        if fname:
            MongoEntregaRepository().definir_assinatura(nota.id, papel, path=fname)
        else:
            MongoEntregaRepository().definir_assinatura(nota.id, papel, limpar=True)
    else:
        setattr(nota, f"assinatura_{papel}_path", fname)


@bp.route("/minha-assinatura", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.TECNICO.value, Perfil.APROVADOR.value, Perfil.TECNICO_ADMIN.value)
def upload_minha_assinatura():
    """Grava o PNG no perfil do utilizador para reutilizar nas próximas notas.

    Aceita duas origens, ambas guardadas como PNG:
      - Ficheiro carregado (multipart/form-data, campo "signature").
      - Assinatura desenhada no canvas (JSON, campo "imagem" com um
        data URL "data:image/png;base64,...").
    """
    if current_user.assinatura_path:
        return jsonify({"error": "Já existe uma assinatura neste perfil. Elimine-a para carregar outra."}), 409

    nome_fixo = f"sig_user_{current_user.id}.png"
    if "signature" in request.files:
        fname, erro = guardar_png(request.files["signature"], nome_fixo=nome_fixo)
        nota_id = request.form.get("nota_id") or None
    else:
        dados = request.get_json(silent=True) or {}
        fname, erro = guardar_dataurl_png(dados.get("imagem"), nome_fixo)
        nota_id = dados.get("nota_id") or None
    if erro:
        return jsonify({"error": erro}), 400
    current_user.assinatura_path = fname
    current_user.assinatura_reutilizavel = True
    _definir_assinatura_auto(nota_id, fname)
    db.session.commit()
    return jsonify({"ok": True, "filename": fname, "url": url_assinatura(fname)})


@bp.route("/minha-assinatura/apagar", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.TECNICO.value, Perfil.APROVADOR.value, Perfil.TECNICO_ADMIN.value)
def apagar_minha_assinatura():
    """Remove a única assinatura do perfil (permite carregar outra)."""
    from app.utils.assinatura import remover_ficheiro

    anterior = current_user.assinatura_path
    current_user.assinatura_path = None
    current_user.assinatura_reutilizavel = False
    _definir_assinatura_auto(request.form.get("nota_id") or None, None)
    db.session.commit()
    if anterior:
        remover_ficheiro(anterior)
    return jsonify({"ok": True})
