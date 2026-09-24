"""CRUD e fluxo das Notas de Saída."""

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
from app.models.nota import NotaSaida
from app.repositories.notas import MongoNotaRepository
from app.services import campos_dinamicos_service, directory_service, nota_service, notificacoes
from app.utils.constants import ESTADOS_LABEL, TIPOS_ITEM, TIPOS_ITEM_COM_SAP, EstadoNota, Perfil
from app.utils.decorators import perfis_requeridos
from app.utils.assinatura import ler_posicao, nome_ficheiro, url_assinatura

bp = Blueprint("notas", __name__, url_prefix="/notas")


@bp.before_request
def _bloquear_admin():
    """O Administrador gere a plataforma (utilizadores, permissões, campos) e
    não cria nem vê notas — isso é exclusivo do Técnico (e do Aprovador, só
    para decidir)."""
    if current_user.is_authenticated and current_user.is_admin():
        flash("Administradores gerem a plataforma e não têm acesso às notas.", "info")
        return redirect(url_for("admin.utilizadores"))


def _consulta_listagem():
    """Filtro «quem pode ver o quê», na forma certa para o backend ativo:
    uma Query SQLAlchemy normalmente, ou um dict de filtro Mongo quando
    USE_MONGO_NOTAS está ligado."""
    if nota_service._mongo_notas_ativo():
        if current_user.perfil == Perfil.APROVADOR.value:
            return {"estado": {"$ne": EstadoNota.RASCUNHO.value}}
        if current_user.is_tecnico():
            return {"$or": [{"criado_por": current_user.id}, {"revisao_tecnico_id": current_user.id}]}
        return {"_id": None}  # nunca corresponde a nada

    if current_user.perfil == Perfil.APROVADOR.value:
        # O aprovador só decide/acompanha notas já submetidas — nunca vê
        # rascunhos que o técnico ainda nem entregou para revisão.
        return NotaSaida.query.filter(NotaSaida.estado != EstadoNota.RASCUNHO.value)
    if current_user.is_tecnico():
        return NotaSaida.query.filter(
            or_(
                NotaSaida.criado_por == current_user.id,
                NotaSaida.revisao_tecnico_id == current_user.id,
            )
        )
    return NotaSaida.query.filter(false())


def _obter_ou_404(nota_id):
    if nota_service._mongo_notas_ativo():
        nota = MongoNotaRepository().obter_por_id(nota_id)
    else:
        try:
            nota = db.session.get(NotaSaida, int(nota_id))
        except (TypeError, ValueError):
            nota = None
    if nota is None:
        abort(404)
    return nota


def _pode_ver(nota):
    if current_user.is_aprovador():
        return nota.estado != EstadoNota.RASCUNHO.value
    if current_user.is_tecnico() and (
        nota.criado_por == current_user.id or nota.revisao_tecnico_id == current_user.id
    ):
        return True
    return False


@bp.route("/")
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

    if nota_service._mongo_notas_ativo():
        from app.utils.pagination import SimplePagination

        encontradas = nota_service.pesquisar_mongo(
            _consulta_listagem(),
            referencia=referencia or None,
            colaborador=colaborador or None,
            estado=estado or None,
            data_inicio=di,
            data_fim=df,
        )
        paginacao = SimplePagination(encontradas, pagina, current_app.config["ITEMS_PER_PAGE"])
        stats = nota_service.estatisticas_mongo(_consulta_listagem())
    else:
        consulta = nota_service.pesquisar(
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
        stats = nota_service.estatisticas(_consulta_listagem())
    return render_template(
        "notas/listar.html",
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
    """Regista na base de dados uma Nota de Saída já existente (PDF externo),
    sem passar pelo formulário completo de criação."""
    form = CarregarNotaForm()
    if not form.validate_on_submit():
        primeiro_erro = next(iter(form.errors.values()), [None])[0]
        flash(primeiro_erro or "Não foi possível carregar a nota. Verifique os dados.", "danger")
        return redirect(url_for("notas.listar"))

    ficheiro = request.files.get(form.ficheiro.name)
    try:
        nota = nota_service.carregar_nota(form.data, ficheiro, current_user)
    except ValueError as erro:
        flash(str(erro), "warning")
        return redirect(url_for("notas.listar"))
    except (IntegrityError, DuplicateKeyError):
        db.session.rollback()
        flash("Já existe uma nota com este número de referência Remedy.", "danger")
        return redirect(url_for("notas.listar"))

    flash("Nota carregada e adicionada à listagem.", "success")
    return redirect(url_for("notas.detalhe", nota_id=nota.id))


@bp.route("/diretorio/pesquisar")
@login_required
@perfis_requeridos(Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value)
def diretorio_pesquisar():
    """Pesquisa de destinatários no diretório da instituição (Active Directory).

    Enquanto não há acesso ao AD do banco, devolve resultados simulados
    (ver app/services/directory_service.py, DIRECTORY_MODE).
    """
    termo = (request.args.get("q") or "").strip()
    if len(termo) < directory_service.TERMO_MINIMO:
        return jsonify({"resultados": []})
    try:
        resultados = directory_service.procurar_pessoas(termo, limite=10)
    except Exception:  # pragma: no cover - falha do diretório não deve rebentar o form
        current_app.logger.exception("Falha ao pesquisar no diretório.")
        return jsonify({"resultados": [], "erro": "Diretório indisponível."}), 502
    return jsonify({"resultados": resultados})


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
    campos_extra = campos_dinamicos_service.listar_aplicaveis("saida")
    valores_extra = _ler_respostas_campos(campos_extra) if request.method == "POST" else {}

    if request.method == "POST" and form.validate():
        itens = nota_service.extrair_itens(request.form)
        faltam = campos_dinamicos_service.validar_obrigatorios("saida", valores_extra)
        if not itens:
            flash("Adicione pelo menos um item de equipamento.", "warning")
        elif faltam:
            flash("Preencha os campos obrigatórios: " + ", ".join(faltam) + ".", "warning")
        elif form.submeter.data and not current_user.assinatura_path:
            flash("Carregue a sua assinatura PNG reutilizável antes de confirmar a nota.", "warning")
        else:
            try:
                pediu_submeter = bool(form.submeter.data)
                form.motivo.data = form.motivo_efetivo()
                nota = nota_service.criar_nota(
                    form.data,
                    itens,
                    current_user,
                    submeter=False,
                    posicao_assinatura=ler_posicao(request.form),
                )
                campos_dinamicos_service.guardar_valores("saida", nota.id, valores_extra)
                if pediu_submeter:
                    flash(
                        "Rascunho criado. Recolha a assinatura «Entregue Por» "
                        "abaixo para submeter para aprovação.",
                        "info",
                    )
                else:
                    flash("Rascunho guardado com sucesso.", "success")
                return redirect(url_for("notas.detalhe", nota_id=nota.id))
            except (IntegrityError, DuplicateKeyError):
                db.session.rollback()
                flash("Já existe uma nota com este número de referência Remedy.", "danger")

    return render_template(
        "notas/formulario.html",
        form=form,
        itens=itens_form,
        tipos_item=TIPOS_ITEM,
        tipos_item_sap=TIPOS_ITEM_COM_SAP,
        campos_extra=campos_extra,
        valores_extra=valores_extra,
        titulo="Nova Nota de Saída",
    )


@bp.route("/<nota_id>/editar", methods=["GET", "POST"])
@login_required
def editar(nota_id):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_editar(current_user):
        abort(403)

    form = NotaForm(obj=nota)
    form.aprovador.choices = nota_service.choices_aprovadores()
    if request.method == "GET" and getattr(nota, "aprovador_designado_id", None):
        form.aprovador.data = str(nota.aprovador_designado_id)
    form.garantir_motivo(nota.motivo)
    itens_form = (
        _itens_do_pedido()
        if request.method == "POST"
        else [
            {
                "tipo_item": i.tipo_item,
                "descricao": i.descricao,
                "numero_serie": i.numero_serie or "",
                "numero_sap": i.numero_sap or "",
                "quantidade": i.quantidade,
            }
            for i in nota.itens
        ]
        or [_item_vazio()]
    )
    campos_extra = campos_dinamicos_service.listar_aplicaveis("saida")
    valores_extra = (
        _ler_respostas_campos(campos_extra)
        if request.method == "POST"
        else campos_dinamicos_service.obter_valores("saida", nota.id)
    )

    if request.method == "POST" and form.validate():
        itens = nota_service.extrair_itens(request.form)
        faltam = campos_dinamicos_service.validar_obrigatorios("saida", valores_extra)
        if not itens:
            flash("Adicione pelo menos um item de equipamento.", "warning")
        elif faltam:
            flash("Preencha os campos obrigatórios: " + ", ".join(faltam) + ".", "warning")
        else:
            try:
                pediu_submeter = bool(form.submeter.data)
                submeter = pediu_submeter and nota.assinaturas_entrega_ok
                if submeter and not (
                    (form.aprovador.data not in (None, "", "0"))
                    or getattr(nota, "aprovador_designado_id", None)
                ):
                    raise ValueError("Seleccione o aprovador a quem enviar a nota.")
                form.motivo.data = form.motivo_efetivo()
                nota = nota_service.atualizar_nota(
                    nota,
                    form.data,
                    itens,
                    current_user,
                    submeter=submeter,
                    aprovador_id=form.aprovador.data,
                    posicao_assinatura=ler_posicao(request.form),
                )
                campos_dinamicos_service.guardar_valores("saida", nota.id, valores_extra)
                if submeter:
                    notificacoes.nota_submetida("saida", nota, current_user)
                    flash("Nota submetida para aprovação.", "success")
                elif pediu_submeter:
                    flash(
                        "Nota guardada. Recolha a assinatura «Entregue Por» "
                        "para submeter para aprovação.",
                        "info",
                    )
                else:
                    flash("Nota atualizada.", "success")
                return redirect(url_for("notas.detalhe", nota_id=nota.id))
            except ValueError as erro:
                db.session.rollback()
                flash(str(erro), "warning")
            except (IntegrityError, DuplicateKeyError):
                db.session.rollback()
                flash("Já existe uma nota com este número de referência Remedy.", "danger")

    return render_template(
        "notas/formulario.html",
        form=form,
        itens=itens_form,
        tipos_item=TIPOS_ITEM,
        tipos_item_sap=TIPOS_ITEM_COM_SAP,
        campos_extra=campos_extra,
        valores_extra=valores_extra,
        titulo=f"Editar Nota {nota.numero_referencia}",
        nota=nota,
    )


@bp.route("/<nota_id>")
@login_required
def detalhe(nota_id):
    nota = _obter_ou_404(nota_id)
    if not _pode_ver(nota):
        abort(403)
    from app.models.historico import Historico

    historico = (
        Historico.query.filter_by(nota_id=nota.id)
        .order_by(Historico.data_hora.desc())
        .all()
    )
    form_decisao = DecisaoForm()
    form_decisao.tecnico_revisao.choices = nota_service.choices_tecnicos()
    form_decisao.tecnico_revisao.data = str(nota.revisao_tecnico_id or nota.criado_por)
    return render_template(
        "notas/detalhe.html",
        nota=nota,
        historico=historico,
        form_decisao=form_decisao,
        aprovadores=nota_service.choices_aprovadores(),
        campos_valores=campos_dinamicos_service.valores_para_exibir("saida", nota.id),
    )


@bp.route("/<nota_id>/email-recetor.eml")
@login_required
def email_recetor(nota_id):
    """Rascunho de e-mail (.eml, não enviado) para o recetor, com o PDF da
    nota concluída em anexo — o Outlook abre-o pronto a enviar."""
    from flask import Response

    nota = _obter_ou_404(nota_id)
    if not _pode_ver(nota) or nota.estado != EstadoNota.CONCLUIDA.value:
        abort(404)
    conteudo = notificacoes.eml_para_recetor("saida", nota, current_user)
    if conteudo is None:
        abort(404)
    nome = f"nota_{nota.numero_referencia or nota.id}.eml"
    return Response(
        conteudo,
        mimetype="message/rfc822",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@bp.route("/<nota_id>/submeter", methods=["POST"])
@login_required
def submeter(nota_id):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        abort(403)
    if not nota.itens:
        flash("Não é possível submeter uma nota sem itens.", "warning")
        return redirect(url_for("notas.detalhe", nota_id=nota.id))
    try:
        nota_service.submeter_nota(nota, current_user, aprovador_id=request.form.get("aprovador_id"))
    except ValueError as erro:
        db.session.rollback()
        flash(str(erro), "warning")
        return redirect(url_for("notas.detalhe", nota_id=nota.id))
    notificacoes.nota_submetida("saida", nota, current_user)
    flash("Nota submetida para aprovação.", "success")
    return redirect(url_for("notas.detalhe", nota_id=nota.id))


@bp.route("/<nota_id>/assinatura/<papel>", methods=["POST"])
@login_required
def guardar_assinatura(nota_id, papel):
    """Recolhe a assinatura da entrega (Entregue Por / Recebido / Segurança)."""
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        return jsonify({"error": "Sem permissão para recolher assinaturas."}), 403
    dados = request.get_json(silent=True) or {}
    estava_aprovada = nota.estado == EstadoNota.APROVADA.value
    try:
        fname = nota_service.guardar_assinatura_papel(
            nota,
            papel,
            dados.get("imagem"),
            current_user,
            posicao=dados.get("posicao"),
        )
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    if papel == "recebido" and estava_aprovada and nota.estado == EstadoNota.CONCLUIDA.value:
        # Última assinatura: nota concluída -> PDF ao recetor, em nome do técnico.
        notificacoes.nota_concluida("saida", nota, current_user)
    return jsonify({"ok": True, "url": url_assinatura(fname)})


@bp.route("/<nota_id>/assinatura/<papel>/remover", methods=["POST"])
@login_required
def remover_assinatura(nota_id, papel):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        return jsonify({"error": "Sem permissão."}), 403
    try:
        nota_service.remover_assinatura_papel(nota, papel, current_user)
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    return jsonify({"ok": True})


@bp.route("/<nota_id>/apagar", methods=["POST"])
@login_required
def apagar(nota_id):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_editar(current_user):
        abort(403)
    nota_service.apagar_nota(nota)
    flash("Nota apagada com sucesso.", "success")
    return redirect(url_for("notas.listar"))


@bp.route("/<nota_id>/assinatura/<papel>/posicao", methods=["POST"])
@login_required
def atualizar_posicao_assinatura(nota_id, papel):
    nota = _obter_ou_404(nota_id)
    if not nota.pode_gerir_assinaturas(current_user):
        return jsonify({"error": "Sem permissão."}), 403
    dados = request.get_json(silent=True) or {}
    try:
        nota_service.atualizar_posicao_assinatura(
            nota, papel, dados.get("posicao"), current_user
        )
    except ValueError as erro:
        return jsonify({"error": str(erro)}), 400
    return jsonify({"ok": True})


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
        caminho = nota_service.garantir_pdf(nota)
    # ?inline=1 é usado para mostrar o PDF num <iframe> na própria página da
    # nota (documento carregado) em vez de forçar a descarga.
    inline = request.args.get("inline") == "1"
    return send_file(
        caminho,
        as_attachment=not inline,
        download_name=f"Nota_Saida_{nota.numero_documento.replace('/', '-')}.pdf",
        mimetype="application/pdf",
    )


def _item_vazio():
    return {"tipo_item": "", "descricao": "", "numero_serie": "", "numero_sap": "", "quantidade": 1}


def _ler_respostas_campos(campos):
    """Lê do POST os valores da secção «Campos adicionais» (nome dos inputs:
    ``campo_<id>``)."""
    return {campo.id: request.form.get(f"campo_{campo.id}") for campo in campos}


@bp.route("/assinaturas/<path:filename>")
@login_required
def servir_assinatura(filename):
    """Serve PNGs da pasta de assinaturas (nome UUID, não enumerável)."""
    nome = nome_ficheiro(filename)
    if not nome:
        abort(404)
    pasta = current_app.config["SIGNATURE_FOLDER"]
    return send_from_directory(pasta, nome)


def _obter_nota_para_auto_assinatura(nota_id):
    if nota_service._mongo_notas_ativo():
        return MongoNotaRepository().obter_por_id(nota_id)
    try:
        return db.session.get(NotaSaida, int(nota_id))
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
    if nota_service._mongo_notas_ativo():
        if fname:
            MongoNotaRepository().definir_assinatura(nota.id, papel, path=fname)
        else:
            MongoNotaRepository().definir_assinatura(nota.id, papel, limpar=True)
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
    from app.services import assinatura_perfil

    if current_user.assinatura_path:
        return jsonify({"error": assinatura_perfil.JA_EXISTE}), 409

    fname, nota_id, erro = assinatura_perfil.ler_png_do_pedido(current_user)
    if erro:
        return jsonify({"error": erro}), 400
    assinatura_perfil.definir_assinatura_perfil(current_user, fname)
    _definir_assinatura_auto(nota_id, fname)
    db.session.commit()
    return jsonify({"ok": True, "filename": fname, "url": url_assinatura(fname)})


@bp.route("/minha-assinatura/apagar", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.TECNICO.value, Perfil.APROVADOR.value, Perfil.TECNICO_ADMIN.value)
def apagar_minha_assinatura():
    """Remove a única assinatura do perfil (permite carregar outra)."""
    from app.services.assinatura_perfil import definir_assinatura_perfil
    from app.utils.assinatura import remover_ficheiro

    anterior = current_user.assinatura_path
    definir_assinatura_perfil(current_user, None)
    _definir_assinatura_auto(request.form.get("nota_id") or None, None)
    db.session.commit()
    if anterior:
        remover_ficheiro(anterior)
    return jsonify({"ok": True})


def _itens_do_pedido():
    itens = nota_service.extrair_itens(request.form)
    return itens or [_item_vazio()]
