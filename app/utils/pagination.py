"""Paginação leve para resultados que já vêm como lista em memória (ex.:
MongoNotaRepository.listar()), com a mesma interface mínima que os
templates já esperam da Pagination do Flask-SQLAlchemy — .items, .page,
.pages, .has_prev, .has_next, .prev_num, .next_num, .total — para que
`render_paginacao_compacta`/`render_paginacao` funcionem sem alterações.
"""

from __future__ import annotations


class SimplePagination:
    def __init__(self, items: list, page: int, per_page: int):
        self.total = len(items)
        self.page = max(int(page or 1), 1)
        self.per_page = per_page
        self.pages = max((self.total + per_page - 1) // per_page, 1)
        self.page = min(self.page, self.pages)
        inicio = (self.page - 1) * per_page
        self.items = items[inicio: inicio + per_page]

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None


# ---------------------------------------------------------------------------
# Nº de linhas por página escolhido pelo utilizador (?por_pagina=5|10|15|todas)
# ---------------------------------------------------------------------------
OPCOES_POR_PAGINA = (5, 10, 15)
POR_PAGINA_OMISSAO = 10


def por_pagina_pedido(total: int | None = None) -> int:
    """Linhas por página pedidas no URL. «todas» devolve o total (mínimo 1);
    qualquer valor fora das opções cai na omissão (10)."""
    from flask import request

    valor = (request.args.get("por_pagina") or "").strip().lower()
    if valor == "todas":
        return max(int(total or 0), 1)
    try:
        numero = int(valor)
    except ValueError:
        return POR_PAGINA_OMISSAO
    return numero if numero in OPCOES_POR_PAGINA else POR_PAGINA_OMISSAO


def paginar_lista(itens: list, pagina) -> "SimplePagination":
    return SimplePagination(itens, pagina, por_pagina_pedido(len(itens)))


def paginar_query(consulta, pagina):
    """Pagination do Flask-SQLAlchemy com o nº de linhas escolhido."""
    from flask import request

    valor = (request.args.get("por_pagina") or "").strip().lower()
    total = consulta.order_by(None).count() if valor == "todas" else None
    return consulta.paginate(page=pagina, per_page=por_pagina_pedido(total), error_out=False)
