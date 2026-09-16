from app import create_app
from app.models.nota import NotaSaida
from app.models.configuracao import Configuracao
from app.services.pdf_service import gerar_pdf
from app.extensions import db
import pymupdf
import os

app = create_app("development")
with app.app_context():
    cfg = Configuracao.obter()
    print("config", cfg.origem_de, cfg.origem_local, cfg.local_emissao, cfg.direcao)
    nota = NotaSaida.query.order_by(NotaSaida.id.asc()).first()
    print("nota", nota.id, nota.numero_documento, nota.numero_referencia, nota.origem_local)
    pasta = app.config["PDF_FOLDER"]
    caminho = gerar_pdf(nota, pasta)
    print("pdf", caminho, os.path.getsize(caminho))
    doc = pymupdf.open(caminho)
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), alpha=False)
    out = os.path.join(pasta, "preview_gerado.png")
    pix.save(out)
    print("preview", out)
