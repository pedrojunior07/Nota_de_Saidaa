"""Relatório de equipamentos entregues — um por módulo (Saída / Entrega).

Todos os perfis podem ver (só leitura). O módulo vem da sessão, tal como o
resto da plataforma; o PDF usa exatamente os mesmos filtros do ecrã.
"""

from datetime import date

from flask import Blueprint, Response, render_template, request, session
from flask_login import current_user, login_required

from app.services import relatorio_service
from app.utils.tempo import agora

bp = Blueprint("relatorios", __name__, url_prefix="/relatorios")

POR_PAGINA = 50


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
    total_paginas = max(1, -(-len(rel.linhas) // POR_PAGINA))
    try:
        pagina = min(max(1, int(request.args.get("pagina", 1))), total_paginas)
    except ValueError:
        pagina = 1
    args = request.args.to_dict()
    args.pop("pagina", None)
    return render_template(
        "relatorios/index.html",
        rel=rel,
        modulo=relatorio_service.MODULOS[tipo],
        periodo=periodo,
        periodos=relatorio_service.PERIODOS,
        linhas_pagina=rel.linhas[(pagina - 1) * POR_PAGINA: pagina * POR_PAGINA],
        pagina=pagina,
        total_paginas=total_paginas,
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
