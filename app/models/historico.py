"""Registo de auditoria das ações sobre as notas."""

from app.extensions import db
from app.utils.tempo import agora


class Historico(db.Model):
    """Trilha de auditoria: quem fez o quê e quando, sobre cada nota."""

    __tablename__ = "historico"

    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(
        db.Integer, db.ForeignKey("notas_saida.id", ondelete="CASCADE"), nullable=False
    )
    utilizador = db.Column(db.String(150), nullable=False)
    acao = db.Column(db.String(255), nullable=False)
    data_hora = db.Column(db.DateTime, nullable=False, default=agora, index=True)

    nota = db.relationship("NotaSaida", back_populates="historico")

    def __repr__(self):
        return f"<Historico {self.acao} @ {self.data_hora}>"
