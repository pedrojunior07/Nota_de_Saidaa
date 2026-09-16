"""Filtros Jinja2 para apresentação de dados."""

from app.utils.constants import ESTADOS_BADGE, ESTADOS_LABEL, PERFIS_LABEL


def estado_label(valor):
    return ESTADOS_LABEL.get(valor, valor or "—")


def estado_badge(valor):
    return ESTADOS_BADGE.get(valor, "secondary")


def perfil_label(valor):
    return PERFIS_LABEL.get(valor, valor or "—")


def formatar_data(valor, com_hora=False):
    if not valor:
        return "—"
    if com_hora:
        return valor.strftime("%d/%m/%Y %H:%M")
    return valor.strftime("%d/%m/%Y")
