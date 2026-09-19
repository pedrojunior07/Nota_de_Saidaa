"""Itens associados a uma Nota de Saída."""

from app.extensions import db


class ItemNota(db.Model):
    """Equipamento ou acessório entregue no âmbito de uma nota."""

    __tablename__ = "itens_nota"

    id = db.Column(db.Integer, primary_key=True)
    nota_id = db.Column(
        db.Integer, db.ForeignKey("notas_saida.id", ondelete="CASCADE"), nullable=False
    )
    tipo_item = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    numero_serie = db.Column(db.String(100), nullable=True)
    numero_sap = db.Column(db.String(100), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False, default=1)

    nota = db.relationship("NotaSaida", back_populates="itens")

    def descricao_impressa(self):
        """Descrição impressa: modelo, seguido de Nr. de Série e SAP sempre
        explícitos (mostra "N/A" quando não aplicável), para nunca ficarem
        escondidos ou ambíguos dentro do texto."""
        serie = self.numero_serie or "N/A"
        sap = self.numero_sap or "N/A"
        return f"{self.descricao} — Nr. Série: {serie} | SAP: {sap}"

    def __repr__(self):
        return f"<ItemNota {self.tipo_item} x{self.quantidade}>"
