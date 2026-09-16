"""Exportação dos modelos para o Flask-Migrate detetar as tabelas."""

from app.models.campo_dinamico import CampoDinamico, ValorCampoDinamico
from app.models.configuracao import Configuracao
from app.models.historico import Historico
from app.models.historico_entrega import HistoricoEntrega
from app.models.item import ItemNota
from app.models.item_entrega import ItemEntrega
from app.models.nota import NotaSaida
from app.models.nota_entrega import NotaEntrega
from app.models.user import User

__all__ = [
    "User",
    "NotaSaida",
    "ItemNota",
    "Historico",
    "Configuracao",
    "NotaEntrega",
    "ItemEntrega",
    "HistoricoEntrega",
    "CampoDinamico",
    "ValorCampoDinamico",
]
