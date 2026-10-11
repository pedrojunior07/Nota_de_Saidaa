"""Devolução de equipamento (SQLite) — um registo por item devolvido.

Associa-se a uma nota concluída (Saída ou Entrega) e ao item devolvido.
Vários itens devolvidos no mesmo momento partilham o mesmo `registo_id`.
Em MongoDB, os mesmos dados ficam no campo `devolucoes` da própria nota.
"""

from app.extensions import db
from app.utils.tempo import agora


class Devolucao(db.Model):
    __tablename__ = "devolucoes"

    id = db.Column(db.Integer, primary_key=True)
    nota_tipo = db.Column(db.String(10), nullable=False)   # "saida" | "entrega"
    nota_id = db.Column(db.String(40), nullable=False)
    item_id = db.Column(db.String(40), nullable=False)
    registo_id = db.Column(db.String(40), nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=agora)
    registado_por_id = db.Column(db.String(40), nullable=True)
    registado_por_nome = db.Column(db.String(150), nullable=True)
    estado_equipamento = db.Column(db.String(30), nullable=True)
    motivo = db.Column(db.String(80), nullable=True)
    observacao = db.Column(db.String(500), nullable=True)

    __table_args__ = (
        db.Index("ix_devolucoes_nota", "nota_tipo", "nota_id"),
        db.Index("ix_devolucoes_registo_id", "registo_id"),
    )
