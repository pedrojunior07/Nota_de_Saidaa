"""Guardar, resolver e servir ficheiros PNG de assinatura."""

import base64
import binascii
import os
import re
import uuid

from flask import current_app, url_for
from werkzeug.utils import secure_filename

EXTENSOES = {".png"}
TAMANHO_MAX = 2 * 1024 * 1024

_DATAURL_PNG = re.compile(r"^data:image/png;base64,(?P<dados>[A-Za-z0-9+/=\s]+)$")


def nome_ficheiro(path):
    if not path:
        return None
    return os.path.basename(str(path).replace("\\", "/"))


def caminho_absoluto(path):
    nome = nome_ficheiro(path)
    if not nome:
        return None
    pasta = current_app.config["SIGNATURE_FOLDER"]
    candidato = os.path.join(pasta, nome)
    if os.path.isfile(candidato):
        return candidato
    legado = os.path.normpath(os.path.join(current_app.root_path, str(path)))
    if os.path.isfile(legado):
        return legado
    return None


def url_assinatura(path):
    nome = nome_ficheiro(path)
    if not nome:
        return None
    return url_for("notas.servir_assinatura", filename=nome)


def remover_ficheiro(path):
    absoluto = caminho_absoluto(path)
    if absoluto and os.path.isfile(absoluto):
        try:
            os.remove(absoluto)
        except OSError:
            pass


def guardar_png(file_storage, nome_fixo=None):
    """Grava um PNG na pasta de assinaturas e devolve só o nome do ficheiro."""
    if file_storage is None or not file_storage.filename:
        return None, "Ficheiro não enviado."
    nome = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(nome)
    if ext.lower() not in EXTENSOES:
        return None, "A assinatura deve ser um ficheiro PNG."
    try:
        file_storage.stream.seek(0, os.SEEK_END)
        tamanho = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if tamanho > TAMANHO_MAX:
            return None, "O PNG não pode exceder 2 MB."
    except Exception:
        file_storage.stream.seek(0)
    pasta = current_app.config["SIGNATURE_FOLDER"]
    os.makedirs(pasta, exist_ok=True)
    fname = nome_fixo or f"sig_{uuid.uuid4().hex}.png"
    destino = os.path.join(pasta, fname)
    if os.path.isfile(destino):
        os.remove(destino)
    file_storage.save(destino)
    return fname, None


def guardar_dataurl_png(dataurl, nome_fixo):
    """Grava um PNG vindo de canvas.toDataURL('image/png'). Devolve (nome, erro)."""
    if not dataurl:
        return None, "Assinatura vazia."
    m = _DATAURL_PNG.match(dataurl.strip())
    if not m:
        return None, "Formato de assinatura inválido (esperado PNG)."
    try:
        binario = base64.b64decode(m.group("dados"), validate=True)
    except (binascii.Error, ValueError):
        return None, "Não foi possível descodificar a assinatura."
    if not binario.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, "O conteúdo não é um PNG válido."
    if len(binario) > TAMANHO_MAX:
        return None, "A assinatura não pode exceder 2 MB."

    pasta = current_app.config["SIGNATURE_FOLDER"]
    os.makedirs(pasta, exist_ok=True)
    fname = secure_filename(nome_fixo) or f"sig_{uuid.uuid4().hex}.png"
    destino = os.path.join(pasta, fname)
    with open(destino, "wb") as f:
        f.write(binario)
    return fname, None


def ler_posicao(formulario, prefixo="assinatura", papel="entregue", tipo="saida"):
    """Lê e valida a posição da assinatura enviada pelo formulário.

    O resultado é sempre enquadrado na área permitida do `papel`/`tipo` (ver
    `app/utils/assinatura_zonas.py`), pelo que nunca invade outra célula
    nem sai da folha.
    """
    from app.utils.assinatura_zonas import enquadrar, posicao_padrao

    padrao = posicao_padrao(papel, tipo)

    def _float(nome):
        bruto = formulario.get(f"{prefixo}_{nome}")
        try:
            valor = float(bruto)
        except (TypeError, ValueError):
            return padrao[nome]
        return max(0.0, min(100.0, valor))

    return enquadrar(papel, {
        "x": _float("x"),
        "y": _float("y"),
        "w": _float("w"),
        "h": _float("h"),
    }, tipo=tipo)
