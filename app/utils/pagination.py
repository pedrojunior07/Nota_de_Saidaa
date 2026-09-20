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
