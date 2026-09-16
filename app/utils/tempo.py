"""Utilitário de data/hora em hora local de Maputo (compatível com SQLite e PostgreSQL)."""

from datetime import datetime
from zoneinfo import ZoneInfo


def agora():
    return datetime.now(ZoneInfo("Africa/Maputo")).replace(tzinfo=None)
