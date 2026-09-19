"""Itens de uma Nota de Entrega (inclui coluna DESTINO do exemplar)."""

from app.extensions import db


class ItemEntrega(db.Model):
    __tablename__ = "itens_entrega"

    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(
        db.Integer, db.ForeignKey("notas_entrega.id", ondelete="CASCADE"), nullable=False
    )
    tipo_item = db.Column(db.String(80), nullable=False)
    destino = db.Column(db.String(200), nullable=True)
    descricao = db.Column(db.String(255), nullable=False)
    numero_serie = db.Column(db.String(100), nullable=True)
    numero_sap = db.Column(db.String(100), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False, default=1)

    nota = db.relationship("NotaEntrega", back_populates="itens")

    def descricao_impressa(self):
        """Descrição impressa: modelo, seguido de Nr. de Série e SAP sempre
        explícitos (mostra "N/A" quando não aplicável), para nunca ficarem
        escondidos ou ambíguos dentro do texto."""
        serie = self.numero_serie or "N/A"
        sap = self.numero_sap or "N/A"
        return f"{self.descricao} — Nr. Série: {serie} | SAP: {sap}"

    def __repr__(self):
        return f"<ItemEntrega {self.tipo_item} x{self.quantidade}>"
