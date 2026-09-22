"""Área de administração: utilizadores, configurações e histórico global."""

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.campo_dinamico import CampoDinamicoForm
from app.forms.user import ConfiguracaoForm, UserForm
from app.models.configuracao import Configuracao
from app.models.historico import Historico
from app.models.user import User
from app.services import campos_dinamicos_service
from app.utils.constants import PERFIS_LABEL, Perfil
from app.utils.decorators import perfis_requeridos

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _nota_exemplo_saida():
    """Nota de Saída fictícia (nunca gravada) só para mostrar o template atual
    do documento na aba «Template de Formulário» das Configurações."""
    from datetime import date

    from app.models.item import ItemNota
    from app.models.nota import NotaSaida

    nota = NotaSaida(
        numero_referencia="REQ000000123456",
        data_emissao=date.today(),
        funcionario="Nome do Colaborador",
        email_funcionario="nome.sobrenome@standardbank.co.mz",
        departamento="Departamento",
        motivo="Nova Atribuição",
        observacao="",
        origem_local="Sede IT",
        local_emissao="Maputo",
    )
    nota.id = 0
    nota.criador = None
    nota.aprovador = None
    nota.itens = [
        ItemNota(descricao="Descrição do equipamento", numero_serie="XXXXXXX", quantidade=1, tipo_item="Outro")
    ]
    return nota


def _nota_exemplo_entrega():
    """Nota de Entrega fictícia (nunca gravada), mesmo propósito da de Saída."""
    from datetime import date

    from app.models.item_entrega import ItemEntrega
    from app.models.nota_entrega import NotaEntrega

    nota = NotaEntrega(
        numero_referencia="REQ000000123456",
        data_emissao=date.today(),
        funcionario="Nome do Destinatário",
        email_funcionario="nome.sobrenome@standardbank.co.mz",
        departamento="Departamento",
        motivo="Nova Atribuição",
        observacao="",
        origem_local="Sede IT",
        local_emissao="Maputo",
    )
    nota.id = 0
    nota.criador = None
    nota.aprovador = None
    nota.seguranca = None
    nota.itens = [
        ItemEntrega(
            descricao="Descrição do equipamento", destino="Balcão / Filial",
            numero_serie="XXXXXXX", quantidade=1, tipo_item="Outro",
        )
    ]
    return nota


def _mongo_users_ativo():
    from app.services.auth_service import _mongo_users_ativo as _flag

    return _flag()


def _obter_utilizador(user_id):
    if _mongo_users_ativo():
        from app.repositories.users import UserRepository

        return UserRepository().get(user_id)
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def _utilizador_tem_notas(user_id):
    """Impede apagar um utilizador que já criou notas — perderia-se a
    referência ao autor. Sugere desativar em vez de apagar nesse caso."""
    from app.models.nota import NotaSaida
    from app.models.nota_entrega import NotaEntrega
    from app.repositories.entrega import MongoEntregaRepository
    from app.repositories.notas import MongoNotaRepository
    from app.services import entrega_service, nota_service

    if nota_service._mongo_notas_ativo():
        if MongoNotaRepository().contar({"criado_por": user_id}) > 0:
            return True
    else:
        try:
            if NotaSaida.query.filter_by(criado_por=int(user_id)).first():
                return True
        except (TypeError, ValueError):
            pass

    if entrega_service._mongo_entrega_ativo():
        if MongoEntregaRepository().contar({"criado_por": user_id}) > 0:
            return True
    else:
        try:
            if NotaEntrega.query.filter_by(criado_por=int(user_id)).first():
                return True
        except (TypeError, ValueError):
            pass
    return False


@bp.route("/utilizadores")
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def utilizadores():
    pagina = request.args.get("pagina", 1, type=int)
    pesquisa = request.args.get("q", "").strip()
    if _mongo_users_ativo():
        from app.repositories.users import UserRepository
        from app.utils.pagination import SimplePagination

        utilizadores_lista = UserRepository().listar(pesquisa or None)
        paginacao = SimplePagination(utilizadores_lista, pagina, 12)
    else:
        consulta = User.query.order_by(User.nome.asc())
        if pesquisa:
            like = f"%{pesquisa}%"
            consulta = consulta.filter(db.or_(User.nome.ilike(like), User.username.ilike(like)))
        paginacao = consulta.paginate(page=pagina, per_page=12, error_out=False)
    return render_template(
        "admin/utilizadores.html", paginacao=paginacao, pesquisa=pesquisa, perfis=PERFIS_LABEL
    )


@bp.route("/utilizadores/novo", methods=["GET", "POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def utilizador_novo():
    form = UserForm()
    modo_local = (current_app.config.get("AUTH_MODE") or "local").lower() == "local"
    if form.validate_on_submit():
        if modo_local and not form.password.data:
            flash("Em modo local defina uma palavra-passe para o novo utilizador.", "warning")
        elif _mongo_users_ativo():
            from app.repositories.users import UserRepository

            UserRepository().criar(
                nome=form.nome.data.strip(),
                username=form.username.data.strip().upper(),
                perfil=form.perfil.data,
                ativo=form.ativo.data,
                password=form.password.data if modo_local else None,
            )
            flash("Utilizador criado com sucesso.", "success")
            return redirect(url_for("admin.utilizadores"))
        else:
            utilizador = User(
                nome=form.nome.data.strip(),
                username=form.username.data.strip().upper(),
                perfil=form.perfil.data,
                ativo=form.ativo.data,
            )
            if modo_local and form.password.data:
                utilizador.definir_password(form.password.data)
            # A assinatura é pessoal: cada utilizador gere a sua própria, não
            # é definida pelo administrador ao criar/editar outra conta.
            db.session.add(utilizador)
            db.session.commit()
            flash("Utilizador criado com sucesso.", "success")
            return redirect(url_for("admin.utilizadores"))
    return render_template(
        "admin/utilizador_form.html",
        form=form,
        titulo="Novo utilizador",
        modo_local=modo_local,
    )


def _atualizar_assinatura_propria(utilizador, form):
    """A assinatura só pode ser gerida pelo próprio utilizador."""
    from app.utils.assinatura import guardar_png

    arquivo = request.files.get(form.assinatura.name)
    if arquivo and arquivo.filename:
        fname, erro = guardar_png(arquivo, nome_fixo=f"sig_user_{utilizador.id}.png")
        if erro:
            flash(erro, "warning")
        else:
            utilizador.assinatura_path = fname
    utilizador.assinatura_reutilizavel = bool(form.assinatura_reutilizavel.data)


@bp.route("/utilizadores/<user_id>/editar", methods=["GET", "POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def utilizador_editar(user_id):
    utilizador = _obter_utilizador(user_id)
    if utilizador is None:
        abort(404)
    form = UserForm(utilizador_original=utilizador, obj=utilizador)
    modo_local = (current_app.config.get("AUTH_MODE") or "local").lower() == "local"
    mongo = _mongo_users_ativo()
    if form.validate_on_submit():
        campos = {
            "nome": form.nome.data.strip(),
            "username": form.username.data.strip().upper(),
            "perfil": form.perfil.data,
            "ativo": form.ativo.data,
        }
        if mongo:
            from app.repositories.users import UserRepository

            if modo_local and form.password.data:
                UserRepository().definir_password(utilizador.id, form.password.data)
            UserRepository().atualizar(utilizador.id, campos)
        else:
            utilizador.nome = campos["nome"]
            utilizador.username = campos["username"]
            utilizador.perfil = campos["perfil"]
            utilizador.ativo = campos["ativo"]
            if modo_local and form.password.data:
                utilizador.definir_password(form.password.data)
            if str(utilizador.id) == str(current_user.id):
                _atualizar_assinatura_propria(utilizador, form)
            db.session.commit()
        flash("Utilizador atualizado.", "success")
        return redirect(url_for("admin.utilizadores"))
    return render_template(
        "admin/utilizador_form.html",
        form=form,
        titulo=f"Editar {utilizador.nome}",
        utilizador=utilizador,
        modo_local=modo_local,
    )


@bp.route("/utilizadores/<user_id>/toggle", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def utilizador_toggle(user_id):
    utilizador = _obter_utilizador(user_id)
    if utilizador is None:
        abort(404)
    if str(utilizador.id) == str(current_user.id):
        flash("Não pode desativar a sua própria conta.", "warning")
        return redirect(url_for("admin.utilizadores"))
    novo_estado = not utilizador.ativo
    if _mongo_users_ativo():
        from app.repositories.users import UserRepository

        UserRepository().definir_estado(utilizador.id, novo_estado)
    else:
        utilizador.ativo = novo_estado
        db.session.commit()
    flash(f"Utilizador {'ativado' if novo_estado else 'desativado'}.", "success")
    return redirect(url_for("admin.utilizadores"))


@bp.route("/utilizadores/<user_id>/apagar", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def utilizador_apagar(user_id):
    utilizador = _obter_utilizador(user_id)
    if utilizador is None:
        abort(404)
    if str(utilizador.id) == str(current_user.id):
        flash("Não pode apagar a sua própria conta.", "warning")
        return redirect(url_for("admin.utilizadores"))
    if _utilizador_tem_notas(utilizador.id):
        flash(
            "Este utilizador já criou notas — não pode ser apagado (perder-se-ia a "
            "referência ao autor). Desative a conta em vez disso.",
            "warning",
        )
        return redirect(url_for("admin.utilizadores"))
    if _mongo_users_ativo():
        from app.repositories.users import UserRepository

        UserRepository().apagar(utilizador.id)
    else:
        db.session.delete(utilizador)
        db.session.commit()
    flash("Utilizador apagado.", "success")
    return redirect(url_for("admin.utilizadores"))


@bp.route("/configuracoes", methods=["GET", "POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def configuracoes():
    config = Configuracao.obter()
    form = ConfiguracaoForm(obj=config)
    if form.validate_on_submit():
        form.populate_obj(config)
        db.session.commit()
        flash("Configurações atualizadas.", "success")
        return redirect(url_for("admin.configuracoes"))
    # O Administrador não tem módulo ativo (não interage com notas) — na aba
    # Template de Formulário escolhe diretamente qual documento quer ver,
    # independente de qualquer módulo.
    doc = request.args.get("doc", "saida")
    if doc not in ("saida", "entrega"):
        doc = "saida"
    campos = campos_dinamicos_service.listar_todos()
    if doc == "entrega":
        campos_modulo = [c for c in campos if c.aplica_entrega]
        nota_exemplo = _nota_exemplo_entrega()
        template_documento = "entrega/_documento.html"
    else:
        campos_modulo = [c for c in campos if c.aplica_saida]
        nota_exemplo = _nota_exemplo_saida()
        template_documento = "notas/_documento.html"
    return render_template(
        "admin/configuracoes.html",
        form=form,
        doc=doc,
        campos_modulo=campos_modulo,
        nota_exemplo=nota_exemplo,
        template_documento=template_documento,
    )


@bp.route("/historico")
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def historico():
    pagina = request.args.get("pagina", 1, type=int)
    utilizador = request.args.get("utilizador", "").strip()
    acao = request.args.get("acao", "").strip()

    consulta = Historico.query
    if utilizador:
        consulta = consulta.filter(Historico.utilizador.ilike(f"%{utilizador}%"))
    if acao:
        consulta = consulta.filter(Historico.acao.ilike(f"%{acao}%"))

    consulta = consulta.order_by(Historico.data_hora.desc())
    paginacao = consulta.paginate(
        page=pagina, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False
    )
    return render_template(
        "admin/historico.html",
        paginacao=paginacao,
        filtros={"utilizador": utilizador, "acao": acao},
    )


# ---------------------------------------------------------------------------
# Construtor de campos adicionais — exclusivo do Administrador (gestão da
# plataforma). Permite acrescentar campos personalizados aos formulários da
# Nota de Saída e/ou da Nota de Entrega, sem tocar em código. Vive na aba
# «Template de Formulário» dentro de Configurações.
# ---------------------------------------------------------------------------

def _voltar_ao_template():
    return redirect(url_for("admin.configuracoes") + "#template")


@bp.route("/campos/novo", methods=["GET", "POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def campos_novo():
    form = CampoDinamicoForm()
    if form.validate_on_submit():
        campos_dinamicos_service.criar(form.data, current_user)
        flash("Campo adicional criado com sucesso.", "success")
        return _voltar_ao_template()
    return render_template(
        "admin/campos_formulario.html", form=form, titulo="Novo campo adicional"
    )


@bp.route("/campos/<int:campo_id>/editar", methods=["GET", "POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def campos_editar(campo_id):
    campo = campos_dinamicos_service.obter(campo_id)
    if campo is None:
        abort(404)
    form = CampoDinamicoForm(obj=campo, campo_original=campo)
    if form.validate_on_submit():
        campos_dinamicos_service.atualizar(campo, form.data)
        flash("Campo adicional atualizado.", "success")
        return _voltar_ao_template()
    return render_template(
        "admin/campos_formulario.html",
        form=form,
        titulo=f"Editar «{campo.rotulo}»",
        campo=campo,
    )


@bp.route("/campos/<int:campo_id>/eliminar", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def campos_eliminar(campo_id):
    campo = campos_dinamicos_service.obter(campo_id)
    if campo is None:
        abort(404)
    try:
        campos_dinamicos_service.remover(campo)
        flash("Campo eliminado.", "success")
    except ValueError as erro:
        flash(str(erro), "warning")
    return _voltar_ao_template()


@bp.route("/campos/<int:campo_id>/toggle", methods=["POST"])
@login_required
@perfis_requeridos(Perfil.ADMINISTRADOR.value, Perfil.TECNICO_ADMIN.value)
def campos_toggle(campo_id):
    campo = campos_dinamicos_service.obter(campo_id)
    if campo is None:
        abort(404)
    campos_dinamicos_service.alternar_ativo(campo)
    flash("Campo ativado." if campo.ativo else "Campo desativado.", "success")
    return _voltar_ao_template()
