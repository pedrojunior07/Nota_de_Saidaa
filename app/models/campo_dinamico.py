"""Campos adicionais configuráveis pelo Administrador.

O Administrador (perfil de gestão da plataforma) pode criar campos
personalizados que aparecem na secção «Campos adicionais» do formulário da
Nota de Saída e/ou da Nota de Entrega. Os valores preenchidos ficam
associados ao documento (`ValorCampoDinamico`), independentemente do tipo.
"""

from app.extensions import db
from app.utils.tempo import agora

# (valor guardado na BD, rótulo mostrado ao Administrador)
# Só 3 tipos, de propósito — mais controlo sobre o que se pode criar
# (ao estilo Google Forms: pergunta de texto, numérica, ou de escolha).
TIPOS_CAMPO = [
    ("texto", "Texto"),
    ("numero", "Número"),
    ("select", "Dropdown (lista de opções)"),
]

TIPOS_CAMPO_VALORES = {valor for valor, _ in TIPOS_CAMPO}


class CampoDinamico(db.Model):
    """Definição de um campo adicional (o «módulo/formulário» que o Admin cria)."""

    __tablename__ = "campos_dinamicos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False, unique=True)
    rotulo = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default="texto")
    opcoes = db.Column(db.Text, nullable=True)
    aplica_saida = db.Column(db.Boolean, nullable=False, default=True)
    aplica_entrega = db.Column(db.Boolean, nullable=False, default=True)
    obrigatorio = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    criado_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=agora)

    criador = db.relationship("User", foreign_keys=[criado_por])

    def lista_opcoes(self):
        """Opções de uma lista «select», uma por linha no campo `opcoes`."""
        if not self.opcoes:
            return []
        return [linha.strip() for linha in self.opcoes.splitlines() if linha.strip()]

    def aplica_a(self, tipo_documento):
        return self.aplica_saida if tipo_documento == "saida" else self.aplica_entrega

    def __repr__(self):
        return f"<CampoDinamico {self.nome} ({self.tipo})>"


class ValorCampoDinamico(db.Model):
    """Valor preenchido de um campo dinâmico numa nota concreta.

    `documento_tipo` + `documento_id` referenciam a nota (NotaSaida ou
    NotaEntrega) sem chave estrangeira direta, porque o mesmo campo pode
    aplicar-se aos dois tipos de documento.
    """

    __tablename__ = "valores_campo_dinamico"

    id = db.Column(db.Integer, primary_key=True)
    campo_id = db.Column(
        db.Integer, db.ForeignKey("campos_dinamicos.id", ondelete="CASCADE"), nullable=False
    )
    documento_tipo = db.Column(db.String(10), nullable=False)  # "saida" | "entrega"
    documento_id = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Text, nullable=True)

    campo = db.relationship("CampoDinamico")

    __table_args__ = (
        db.UniqueConstraint(
            "campo_id", "documento_tipo", "documento_id", name="uq_valor_campo_documento"
        ),
        db.Index("ix_valores_campo_documento", "documento_tipo", "documento_id"),
    )

    def __repr__(self):
        return f"<ValorCampoDinamico campo={self.campo_id} doc={self.documento_tipo}:{self.documento_id}>"
