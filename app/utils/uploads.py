"""Guardar ficheiros PDF enviados manualmente (notas carregadas / importadas)."""

import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename

EXTENSOES_PDF = {".pdf"}
TAMANHO_MAX_PDF = 15 * 1024 * 1024


def guardar_pdf_upload(file_storage):
    """Grava um PDF enviado pelo utilizador na pasta de PDFs oficiais.

    Devolve (caminho_absoluto, erro) — o caminho segue a mesma convenção de
    `NotaSaida.pdf_path` usada pelo gerador institucional (caminho completo,
    não só o nome do ficheiro).
    """
    if file_storage is None or not file_storage.filename:
        return None, "Ficheiro não enviado."
    nome = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(nome)
    if ext.lower() not in EXTENSOES_PDF:
        return None, "O ficheiro deve ser um PDF."
    try:
        file_storage.stream.seek(0, os.SEEK_END)
        tamanho = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if tamanho > TAMANHO_MAX_PDF:
            return None, "O PDF não pode exceder 15 MB."
    except Exception:
        file_storage.stream.seek(0)

    pasta = current_app.config["PDF_FOLDER"]
    os.makedirs(pasta, exist_ok=True)
    fname = f"nota_carregada_{uuid.uuid4().hex}.pdf"
    destino = os.path.join(pasta, fname)
    file_storage.save(destino)
    return destino, None
