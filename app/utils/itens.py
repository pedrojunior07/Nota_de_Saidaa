"""Texto de um item de equipamento nas notas (documento na página e PDF)."""


def titulo_item(tipo_item, descricao) -> str:
    """'Carregador — Dell'. Sem repetir o tipo se a descrição já começar por
    ele (ex.: 'Monitor Dell 24'), e sem traço se faltar uma das partes."""
    tipo = (tipo_item or "").strip()
    desc = (descricao or "").strip()
    if not tipo:
        return desc
    if not desc or desc.lower().startswith(tipo.lower()):
        return desc or tipo
    return f"{tipo} — {desc}"
