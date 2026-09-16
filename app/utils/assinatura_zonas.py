"""Mapa dos campos de assinatura, partilhado pelo preview HTML, pelo
posicionador e pela geração do PDF. `app/static/js/signature_zones.js`
espelha estes valores no cliente.

Coordenadas em % da página A4, origem no canto superior esquerdo, Y para baixo.

  - "saida"   → grelha 2x2:
        Autorizado Por (aprovador)  |  Recebido (recebido)
        Entregue Por  (entregue)    |  Segurança (seguranca)
  - "entrega" → assinaturas empilhadas na coluna esquerda, pela ordem
        Autorizado por · Entregue por · Recebido por · Segurança
"""

# Geometria do campo impresso de cada assinatura (rótulo + linha + nome).
#   cx        centro horizontal da linha (%);
#   linha_y   posição vertical da linha onde se assina (%);
#   rotulo_y  linha de base do rótulo, acima da linha (%);
#   nome_y    linha de base do nome, abaixo da linha (%).
_CAMPOS = {
    "saida": {
        "aprovador": {"rotulo": "Autorizado Por", "cx": 32.5, "linha_y": 72.5, "rotulo_y": 65.0, "nome_y": 74.6},
        "recebido": {"rotulo": "Recebido", "cx": 75.0, "linha_y": 72.5, "rotulo_y": 65.0, "nome_y": 74.6},
        "entregue": {"rotulo": "Entregue Por", "cx": 32.5, "linha_y": 89.0, "rotulo_y": 81.5, "nome_y": 91.1},
        "seguranca": {"rotulo": "Segurança", "cx": 75.0, "linha_y": 89.0, "rotulo_y": 81.5, "nome_y": 91.1},
    },
    "entrega": {
        "aprovador": {"rotulo": "Autorizado por", "cx": 25.0, "linha_y": 58.0, "rotulo_y": 51.5, "nome_y": 60.0},
        "entregue": {"rotulo": "Entregue por", "cx": 25.0, "linha_y": 68.0, "rotulo_y": 61.5, "nome_y": 70.0},
        "recebido": {"rotulo": "Recebido por", "cx": 25.0, "linha_y": 78.0, "rotulo_y": 71.5, "nome_y": 80.0},
        "seguranca": {"rotulo": "Segurança", "cx": 25.0, "linha_y": 88.0, "rotulo_y": 81.5, "nome_y": 90.0},
    },
}

# Largura da linha impressa (e da coluna útil), em % da página, centrada em cx.
_LINHA_LARGURA = {"saida": 32.0, "entrega": 40.0}

_MARGEM_ACIMA = {"saida": 9.0, "entrega": 6.0}   # sobe até aqui acima da linha
_MARGEM_ABAIXO = 3.0    # e pode descer só um pouco abaixo da linha
_BASE_ACIMA_LINHA = 1.5
_BASE_ABAIXO_LINHA = 1.0
_ALTURA_PADRAO = {"saida": 7.0, "entrega": 5.5}
_LARGURA_PADRAO = {"saida": 30.0, "entrega": 36.0}

LARGURA_MINIMA = 8.0
ALTURA_MINIMA = 4.0


def _construir_zonas(tipo):
    lw = _LINHA_LARGURA[tipo]
    acima = _MARGEM_ACIMA[tipo]
    return {
        papel: {
            "x_min": round(c["cx"] - lw / 2 - 3, 2),
            "x_max": round(c["cx"] + lw / 2 + 3, 2),
            "y_min": round(c["linha_y"] - acima, 2),
            "y_max": round(c["linha_y"] + _MARGEM_ABAIXO, 2),
        }
        for papel, c in _CAMPOS[tipo].items()
    }


def _construir_defaults(tipo):
    w = _LARGURA_PADRAO[tipo]
    h = _ALTURA_PADRAO[tipo]
    return {
        papel: {
            "x": round(c["cx"] - w / 2, 2),
            "y": round(c["linha_y"] - h, 2),
            "w": w,
            "h": h,
        }
        for papel, c in _CAMPOS[tipo].items()
    }


_ZONAS = {t: _construir_zonas(t) for t in _CAMPOS}
_DEFAULTS = {t: _construir_defaults(t) for t in _CAMPOS}

# Compatibilidade: nomes antigos = variante "saida".
CAMPOS_ASSINATURA = _CAMPOS["saida"]
ZONAS_ASSINATURA = _ZONAS["saida"]
DEFAULTS_ASSINATURA = _DEFAULTS["saida"]
LINHA_LARGURA = _LINHA_LARGURA["saida"]

CAMPOS_ASSINATURA_ENTREGA = _CAMPOS["entrega"]
ZONAS_ASSINATURA_ENTREGA = _ZONAS["entrega"]
DEFAULTS_ASSINATURA_ENTREGA = _DEFAULTS["entrega"]
LINHA_LARGURA_ENTREGA = _LINHA_LARGURA["entrega"]


def campos(tipo="saida"):
    return _CAMPOS.get(tipo, _CAMPOS["saida"])


def largura_linha(tipo="saida"):
    return _LINHA_LARGURA.get(tipo, _LINHA_LARGURA["saida"])


def zona(papel, tipo="saida"):
    return _ZONAS.get(tipo, _ZONAS["saida"]).get(papel)


def posicao_padrao(papel, tipo="saida"):
    tabela = _DEFAULTS.get(tipo, _DEFAULTS["saida"])
    base = tabela.get(papel) or tabela.get("entregue") or next(iter(tabela.values()))
    return dict(base)


def _limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def enquadrar(papel, posicao, tipo="saida"):
    """Ajusta `posicao` (dict x/y/w/h em %) para caber na área do papel e
    encostar a base da assinatura à linha impressa (mantém-nas niveladas)."""
    zonas = _ZONAS.get(tipo, _ZONAS["saida"])
    campos_tipo = _CAMPOS.get(tipo, _CAMPOS["saida"])
    z = zonas.get(papel)
    try:
        x = float(posicao.get("x"))
        y = float(posicao.get("y"))
        w = float(posicao.get("w"))
        h = float(posicao.get("h"))
    except (AttributeError, TypeError, ValueError):
        return posicao_padrao(papel, tipo)

    if not z:
        w = _limitar(w, LARGURA_MINIMA, 100.0)
        h = _limitar(h, ALTURA_MINIMA, 100.0)
        x = _limitar(x, 0.0, 100.0 - w)
        y = _limitar(y, 0.0, 100.0 - h)
        return {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)}

    w = _limitar(w, LARGURA_MINIMA, z["x_max"] - z["x_min"])
    h = _limitar(h, ALTURA_MINIMA, z["y_max"] - z["y_min"])
    x = _limitar(x, z["x_min"], z["x_max"] - w)
    y = _limitar(y, z["y_min"], z["y_max"] - h)

    campo = campos_tipo.get(papel)
    if campo:
        base = _limitar(y + h,
                        campo["linha_y"] - _BASE_ACIMA_LINHA,
                        campo["linha_y"] + _BASE_ABAIXO_LINHA)
        y = _limitar(base - h, z["y_min"], z["y_max"] - h)

    return {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)}
