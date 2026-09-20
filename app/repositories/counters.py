"""Contadores atómicos (equivalente ao id auto-incremental do SQL).

O MongoDB não tem um "id sequencial" nativo como o SQLite/Postgres — os
_id são ObjectId. Para manter o mesmo formato de numero_documento impresso
("000006/2026") usamos uma coleção `counters` com um documento por
contador, incrementado atomicamente via find_one_and_update($inc), que é
seguro mesmo com pedidos em simultâneo (ao contrário de "ler o máximo
atual e somar 1").
"""

from __future__ import annotations

from pymongo import ReturnDocument

from app.repositories.base import get_db


def proximo_valor(nome: str) -> int:
    """Incrementa e devolve o próximo valor do contador `nome`.

    Cria o contador a 1 na primeira chamada (upsert). Ex.: nome
    "notas_saida_2026" dá 1, 2, 3, ... para as notas de saída criadas
    em 2026.
    """
    db = get_db()
    doc = db.counters.find_one_and_update(
        {"_id": nome},
        {"$inc": {"valor": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["valor"]
