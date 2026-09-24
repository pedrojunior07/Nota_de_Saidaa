"""Modelo de utilizador autenticável."""

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.utils.constants import Perfil
from app.utils.tempo import agora


class User(UserMixin, db.Model):
    """Utilizador do sistema (Admin, Técnico, Aprovador ou Técnico Admin)."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # Nome completo — não é introduzido pelo administrador: é preenchido (e
    # mantido atualizado) no login, com o firstName/lastName devolvido pela API
    # de autenticação. Fica vazio até ao primeiro login do utilizador.
    nome = db.Column(db.String(150), nullable=True)
    # Nome de utilizador = nº de colaborador (ex.: A272754). Identificador de login.
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    # Só usado no modo AUTH_MODE=local (dev). Em produção a palavra-passe é validada
    # no Active Directory e não fica guardada.
    password_hash = db.Column(db.String(256), nullable=True)
    perfil = db.Column(db.String(30), nullable=False, default=Perfil.TECNICO.value)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=agora)
    assinatura_path = db.Column(db.String(255), nullable=True)
    assinatura_reutilizavel = db.Column(db.Boolean, nullable=False, default=False)

    notas_criadas = db.relationship(
        "NotaSaida",
        back_populates="criador",
        foreign_keys="NotaSaida.criado_por",
        lazy="dynamic",
    )
    notas_aprovadas = db.relationship(
        "NotaSaida",
        back_populates="aprovador",
        foreign_keys="NotaSaida.aprovado_por",
        lazy="dynamic",
    )

    @property
    def nome_exibicao(self):
        """Nome a mostrar: o nome real, ou o nº de colaborador enquanto o
        utilizador ainda não fez o primeiro login."""
        return self.nome or self.username

    def definir_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verificar_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """Gestor puro da plataforma — não inclui o Técnico Admin de propósito:
        só o Admin fica sem acesso nenhum às notas."""
        return self.perfil == Perfil.ADMINISTRADOR.value

    def is_tecnico(self):
        """O Técnico Admin acumula todas as capacidades do Técnico sobre notas."""
        return self.perfil in (Perfil.TECNICO.value, Perfil.TECNICO_ADMIN.value)

    def is_aprovador(self):
        return self.perfil == Perfil.APROVADOR.value

    def is_tecnico_admin(self):
        return self.perfil == Perfil.TECNICO_ADMIN.value

    def pode_gerir_plataforma(self):
        """Acesso a Utilizadores / Histórico / Configurações: Admin e Técnico Admin."""
        return self.is_admin() or self.is_tecnico_admin()

    def __repr__(self):
        return f"<User {self.username} ({self.perfil})>"
