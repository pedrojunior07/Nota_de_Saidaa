"""Relatório de equipamentos entregues — um por módulo (Saída / Entrega).

Técnicos, Técnicos Admin e Aprovadores podem ver (só leitura); o
Administrador puro não. O módulo vem da sessão, tal como o
resto da plataforma; o PDF usa exatamente os mesmos filtros do ecrã.
"""

from datetime import date

from flask import Blueprint, Response, render_template, request, session
from flask_login import current_user, login_required

from app.services import relatorio_service
from app.utils.pagination import paginar_lista
from app.utils.tempo import agora

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")


@bp.before_request
def _bloquear_admin():
    """O Administrador puro não tem o relatório (o Técnico Admin tem)."""
    if current_user.is_authenticated and current_user.is_admin():
        from flask import redirect, url_for

        return redirect(url_for("admin.utilizadores"))


def _data(nome):
    try:
        return date.fromisoformat(request.args.get(nome, ""))
    except ValueError:
        return None


def _pedido():
    tipo = session.get("modulo") if session.get("modulo") in relatorio_service.MODULOS else "saida"
    periodo = request.args.get("periodo", "mes")
    if periodo not in relatorio_service.PERIODOS:
        periodo = "mes"
    inicio, fim = relatorio_service.intervalo(periodo, _data("inicio"), _data("fim"), hoje=agora().date())
    filtros = {k: request.args.get(k, "") for k in relatorio_service.FILTROS_TEXTO}
    return tipo, periodo, relatorio_service.gerar(tipo, inicio, fim, filtros)


@bp.route("/")
@login_required
def index():
    tipo, periodo, rel = _pedido()
    try:
        pagina = int(request.args.get("pagina", 1))
    except ValueError:
        pagina = 1
    paginacao = paginar_lista(rel.linhas, pagina)
    args = request.args.to_dict()
    args.pop("pagina", None)
    return render_template(
        "relatorios/index.html",
        rel=rel,
        modulo=relatorio_service.MODULOS[tipo],
        periodo=periodo,
        periodos=relatorio_service.PERIODOS,
        icones_tipo=relatorio_service.ICONES_TIPO,
        icone_omissao=relatorio_service.ICONE_TIPO_OMISSAO,
        paginacao=paginacao,
        args=args,
    )


@bp.route("/pdf")
@login_required
def pdf():
    from app.models.configuracao import Configuracao
    from app.services.relatorio_pdf import gerar_pdf

    tipo, _periodo, rel = _pedido()
    try:
        origem = Configuracao.obter().origem_local or "Sede IT"
    except Exception:  # noqa: BLE001 — a configuração é só um pormenor do cabeçalho
        origem = "Sede IT"
    conteudo = gerar_pdf(
        rel,
        gerado_por=current_user.nome_exibicao,
        gerado_em=agora().strftime("%d/%m/%Y %H:%M"),
        origem=origem,
    )
    nome = f"relatorio_equipamentos_{tipo}_{rel.inicio:%Y%m%d}-{rel.fim:%Y%m%d}.pdf"
    return Response(conteudo, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
