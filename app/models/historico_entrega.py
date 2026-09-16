"""Trilha de auditoria das Notas de Entrega."""

from app.extensions import db
from app.utils.tempo import agora


class HistoricoEntrega(db.Model):
    __tablename__ = "historico_entrega"

    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(
        db.Integer, db.ForeignKey("notas_entrega.id", ondelete="CASCADE"), nullable=False
    )
    utilizador = db.Column(db.String(150), nullable=False)
    acao = db.Column(db.String(255), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False, default=agora, index=True)

    nota = db.relationship("NotaEntrega", back_populates="historico")

    def __repr__(self):
        return f"<HistoricoEntrega {self.acao} @ {self.data_hora}>"
