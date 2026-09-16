"""Modelo da Nota de Saída."""

import re

from app.extensions import db
from app.utils.constants import EstadoNota
from app.utils.tempo import agora


class NotaSaida(db.Model):
    """Documento digital que formaliza a entrega de equipamento de TI."""

    __tablename__ = "notas_saida"

    id = db.Column(db.Integer, primary_key=True)
    numero_referencia = db.Column(db.String(50), unique=True, nullable=False, index=True)
    data_emissao = db.Column(db.Date, nullable=False)
    funcionario = db.Column(db.String(150), nullable=False, index=True)
    email_funcionario = db.Column(db.String(150), nullable=False, index=True)
    departamento = db.Column(db.String(120), nullable=False)
    motivo = db.Column(db.String(200), nullable=False)
    observacao = db.Column(db.Text)
    estado = db.Column(
        db.String(30),
        nullable=False,
        default=EstadoNota.RASCUNHO.value,
        index=True,
    )
    criado_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    aprovado_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    data_aprovacao = db.Column(db.DateTime, nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=agora)

    # Campos de suporte ao fluxo digital e à geração de PDF
    data_conclusao = db.Column(db.DateTime, nullable=True)
    pdf_path = db.Column(db.String(255), nullable=True)
    # Nota registada a partir de um PDF externo carregado pelo utilizador (ver
    # nota_service.carregar_nota) — o PDF nunca é regenerado/substituído.
    pdf_carregado = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    comentario_decisao = db.Column(db.Text, nullable=True)
    origem_local = db.Column(db.String(120), nullable=False, default="Sede IT", server_default="Sede IT")
    local_emissao = db.Column(db.String(80), nullable=False, default="Maputo", server_default="Maputo")
    assinatura_entregue_path = db.Column(db.String(255), nullable=True)
    assinatura_aprovador_path = db.Column(db.String(255), nullable=True)
    # assinaturas recolhidas na entrega (signature pad)
    assinatura_recebido_path = db.Column(db.String(255), nullable=True)
    assinatura_seguranca_path = db.Column(db.String(255), nullable=True)
    # posição/escala da assinatura (percentagens relativas à folha)
    assinatura_entregue_x = db.Column(db.Float, nullable=True)
    assinatura_entregue_y = db.Column(db.Float, nullable=True)
    assinatura_entregue_w = db.Column(db.Float, nullable=True)
    assinatura_entregue_h = db.Column(db.Float, nullable=True)
    assinatura_aprovador_x = db.Column(db.Float, nullable=True)
    assinatura_aprovador_y = db.Column(db.Float, nullable=True)
    assinatura_aprovador_w = db.Column(db.Float, nullable=True)
    assinatura_aprovador_h = db.Column(db.Float, nullable=True)
    assinatura_recebido_x = db.Column(db.Float, nullable=True)
    assinatura_recebido_y = db.Column(db.Float, nullable=True)
    assinatura_recebido_w = db.Column(db.Float, nullable=True)
    assinatura_recebido_h = db.Column(db.Float, nullable=True)
    assinatura_seguranca_x = db.Column(db.Float, nullable=True)
    assinatura_seguranca_y = db.Column(db.Float, nullable=True)
    assinatura_seguranca_w = db.Column(db.Float, nullable=True)
    assinatura_seguranca_h = db.Column(db.Float, nullable=True)
    revisao_tecnico_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    @property
    def numero_documento(self):
        """Número impresso no papel: 000003/2026."""
        ano = self.data_emissao.year if self.data_emissao else 2026
        return f"{self.id:06d}/{ano}"

    @property
    def numero_remedy(self):
        """Número Remedy impresso com o prefixo institucional REQ."""
        digitos = re.sub(r"\D", "", self.numero_referencia or "")
        return f"REQ{digitos}" if digitos else "REQ"

    criador = db.relationship(
        "User", foreign_keys=[criado_por], back_populates="notas_criadas"
    )
    aprovador = db.relationship(
        "User", foreign_keys=[aprovado_por], back_populates="notas_aprovadas"
    )
    revisao_tecnico = db.relationship("User", foreign_keys=[revisao_tecnico_id])
    itens = db.relationship(
        "ItemNota",
        back_populates="nota",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ItemNota.id",
    )
    historico = db.relationship(
        "Historico",
        back_populates="nota",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def ultima_alteracao(self):
        """Data da última ação registada sobre a nota."""
        from app.models.historico import Historico

        ultima_acao = (
            self.historico.order_by(Historico.data_hora.desc()).first()
        )
        return ultima_acao.data_hora if ultima_acao else self.data_criacao

    def pode_editar(self, utilizador):
        """Rascunhos, rejeitadas e em revisão podem ser editados pelo técnico
        responsável. O Administrador gere a plataforma e não interage com
        notas (não cria, não vê, não edita)."""
        if not utilizador.is_authenticated:
            return False
        estados_editaveis = {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
        }
        if self.estado not in estados_editaveis:
            return False
        if utilizador.id == self.criado_por:
            return True
        return self.revisao_tecnico_id == utilizador.id

    @property
    def assinaturas_entrega_ok(self):
        """Antes de submeter para aprovação basta a assinatura «Entregue Por»
        (técnico, que criou a nota). O Aprovador assina em segundo lugar e o
        «Recebido» (recetor) assina por último, depois da aprovação. A da
        Segurança é opcional e pode ser recolhida em qualquer momento."""
        return bool(self.assinatura_entregue_path)

    @property
    def numero_assinaturas(self):
        return sum(
            1
            for p in (
                self.assinatura_entregue_path,
                self.assinatura_recebido_path,
                self.assinatura_seguranca_path,
                self.assinatura_aprovador_path,
            )
            if p
        )

    def pode_submeter(self, utilizador):
        if self.estado not in {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
        }:
            return False
        if not self.pode_editar(utilizador):
            return False
        return self.assinaturas_entrega_ok

    def pode_gerir_assinaturas(self, utilizador):
        """Quem recolhe as assinaturas da entrega (técnico responsável).

        Inclui o estado APROVADA porque, depois do Aprovador assinar, ainda é
        preciso recolher a assinatura de «Recebido» (e, opcionalmente, a da
        Segurança) para a nota ficar concluída."""
        if not utilizador.is_authenticated:
            return False
        if self.estado not in {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
            EstadoNota.APROVADA.value,
        }:
            return False
        return utilizador.is_tecnico() and (
            utilizador.id == self.criado_por
            or self.revisao_tecnico_id == utilizador.id
        )

    def pode_recolher_recebido(self, utilizador):
        """A assinatura de «Recebido» só é recolhida depois da aprovação
        (o Aprovador assina em segundo lugar, antes do recetor)."""
        return (
            self.estado == EstadoNota.APROVADA.value
            and not self.assinatura_recebido_path
            and self.pode_gerir_assinaturas(utilizador)
        )

    def pode_aprovar(self, utilizador):
        # A aprovação de notas é exclusiva do perfil Aprovador (o Técnico Admin
        # gere o sistema mas não aprova, por segregação de funções).
        return (
            self.estado == EstadoNota.PENDENTE_APROVACAO.value
            and utilizador.is_aprovador()
        )

    def __repr__(self):
        return f"<NotaSaida {self.numero_referencia} ({self.estado})>"
