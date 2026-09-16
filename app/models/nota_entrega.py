"""Modelo da Nota de Entrega.

Tabela própria (`notas_entrega`), independente da Nota de Saída. Ordem das
assinaturas: **Técnico** (que cria a nota, assina «Entregue Por») → **Aprovador**
(assina «Autorizado por») → **Recebido** (recetor) — esta última é quem
conclui a nota (CONCLUÍDA). A do **Segurança** é opcional e pode ser
recolhida a qualquer momento antes da conclusão; não bloqueia nada.
"""

import re

from app.extensions import db
from app.utils.constants import EstadoNota
from app.utils.tempo import agora


class NotaEntrega(db.Model):
    __tablename__ = "notas_entrega"

    id = db.Column(db.Integer, primary_key=True)
    numero_referencia = db.Column(db.String(50), unique=True, nullable=False, index=True)
    data_emissao = db.Column(db.Date, nullable=False)
    # Destinatário / «Att:» do documento
    funcionario = db.Column(db.String(150), nullable=False, index=True)
    email_funcionario = db.Column(db.String(150), nullable=False, index=True)
    departamento = db.Column(db.String(120), nullable=False)
    motivo = db.Column(db.String(200), nullable=False)
    observacao = db.Column(db.Text)  # linha «NB:» do exemplar
    estado = db.Column(db.String(30), nullable=False, default=EstadoNota.RASCUNHO.value, index=True)

    criado_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    aprovado_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    seguranca_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    revisao_tecnico_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    data_aprovacao = db.Column(db.DateTime, nullable=True)
    data_seguranca = db.Column(db.DateTime, nullable=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=agora)

    pdf_path = db.Column(db.String(255), nullable=True)
    comentario_decisao = db.Column(db.Text, nullable=True)
    origem_local = db.Column(db.String(120), nullable=False, default="Sede IT", server_default="Sede IT")
    local_emissao = db.Column(db.String(80), nullable=False, default="Maputo", server_default="Maputo")

    assinatura_entregue_path = db.Column(db.String(255), nullable=True)
    assinatura_recebido_path = db.Column(db.String(255), nullable=True)
    assinatura_aprovador_path = db.Column(db.String(255), nullable=True)
    assinatura_seguranca_path = db.Column(db.String(255), nullable=True)
    # posição/escala de cada assinatura (percentagens relativas à folha)
    assinatura_entregue_x = db.Column(db.Float, nullable=True)
    assinatura_entregue_y = db.Column(db.Float, nullable=True)
    assinatura_entregue_w = db.Column(db.Float, nullable=True)
    assinatura_entregue_h = db.Column(db.Float, nullable=True)
    assinatura_recebido_x = db.Column(db.Float, nullable=True)
    assinatura_recebido_y = db.Column(db.Float, nullable=True)
    assinatura_recebido_w = db.Column(db.Float, nullable=True)
    assinatura_recebido_h = db.Column(db.Float, nullable=True)
    assinatura_aprovador_x = db.Column(db.Float, nullable=True)
    assinatura_aprovador_y = db.Column(db.Float, nullable=True)
    assinatura_aprovador_w = db.Column(db.Float, nullable=True)
    assinatura_aprovador_h = db.Column(db.Float, nullable=True)
    assinatura_seguranca_x = db.Column(db.Float, nullable=True)
    assinatura_seguranca_y = db.Column(db.Float, nullable=True)
    assinatura_seguranca_w = db.Column(db.Float, nullable=True)
    assinatura_seguranca_h = db.Column(db.Float, nullable=True)

    criador = db.relationship("User", foreign_keys=[criado_por])
    aprovador = db.relationship("User", foreign_keys=[aprovado_por])
    seguranca = db.relationship("User", foreign_keys=[seguranca_por])
    revisao_tecnico = db.relationship("User", foreign_keys=[revisao_tecnico_id])
    itens = db.relationship(
        "ItemEntrega",
        back_populates="nota",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ItemEntrega.id",
    )
    historico = db.relationship(
        "HistoricoEntrega",
        back_populates="nota",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # ------------------------------------------------------------------ #

    @property
    def numero_documento(self):
        ano = self.data_emissao.year if self.data_emissao else 2026
        return f"{self.id:06d}/{ano}"

    @property
    def numero_remedy(self):
        digitos = re.sub(r"\D", "", self.numero_referencia or "")
        return f"REQ{digitos}" if digitos else "REQ"

    @property
    def ultima_alteracao(self):
        from app.models.historico_entrega import HistoricoEntrega

        ultima = self.historico.order_by(HistoricoEntrega.data_hora.desc()).first()
        return ultima.data_hora if ultima else self.data_criacao

    @property
    def numero_assinaturas(self):
        return sum(
            1
            for p in (
                self.assinatura_entregue_path,
                self.assinatura_recebido_path,
                self.assinatura_aprovador_path,
                self.assinatura_seguranca_path,
            )
            if p
        )

    @property
    def assinaturas_entrega_ok(self):
        """Antes de submeter para aprovação basta a assinatura «Entregue Por»
        (técnico). O Aprovador assina em segundo lugar e «Recebido» assina
        depois da aprovação, concluindo a nota. A do Segurança é opcional."""
        return bool(self.assinatura_entregue_path)

    def pode_editar(self, utilizador):
        """Rascunhos, rejeitadas e em revisão podem ser editados pelo técnico
        responsável. O Administrador gere a plataforma e não interage com
        notas (não cria, não vê, não edita)."""
        if not utilizador.is_authenticated:
            return False
        if self.estado not in {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
        }:
            return False
        return utilizador.id == self.criado_por or self.revisao_tecnico_id == utilizador.id

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
        """Recolha de «Entregue Por» (rascunho) e, depois de aprovada, de
        «Recebido» e «Segurança». Sempre pelo técnico responsável."""
        if not utilizador.is_authenticated:
            return False
        estados_ok = {
            EstadoNota.RASCUNHO.value,
            EstadoNota.REJEITADA.value,
            EstadoNota.EM_REVISAO.value,
            EstadoNota.APROVADA.value,
        }
        if self.estado not in estados_ok:
            return False
        return utilizador.is_tecnico() and (
            utilizador.id == self.criado_por or self.revisao_tecnico_id == utilizador.id
        )

    def pode_recolher_recebido(self, utilizador):
        """A assinatura de «Recebido» só é recolhida depois da aprovação
        (o Aprovador assina em segundo lugar, antes do recetor)."""
        return (
            self.estado == EstadoNota.APROVADA.value
            and not self.assinatura_recebido_path
            and self.pode_gerir_assinaturas(utilizador)
        )

    def pode_recolher_seguranca(self, utilizador):
        """A assinatura do Segurança é opcional: pode ser recolhida a
        qualquer momento (antes ou depois da aprovação) enquanto a nota não
        estiver concluída. Não bloqueia a submissão nem a conclusão."""
        return not self.assinatura_seguranca_path and self.pode_gerir_assinaturas(utilizador)

    def pode_aprovar(self, utilizador):
        return (
            self.estado == EstadoNota.PENDENTE_APROVACAO.value
            and utilizador.is_aprovador()
        )

    def __repr__(self):
        return f"<NotaEntrega {self.numero_referencia} ({self.estado})>"
