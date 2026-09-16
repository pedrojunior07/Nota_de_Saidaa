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
        texto = self.descricao
        if self.numero_serie:
            texto = f"{texto}:{self.numero_serie}"
        if self.numero_sap:
            texto = f"{texto} (SAP: {self.numero_sap})"
        return texto

    def __repr__(self):
        return f"<ItemNota {self.tipo_item} x{self.quantidade}>"
