"""Formulários de gestão de utilizadores e configurações."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, Regexp, ValidationError

from app.models.user import User
from app.services.auth_service import _mongo_users_ativo
from app.utils.constants import PERFIS_LABEL


def _normalizar_username(valor):
    return valor.strip().upper() if isinstance(valor, str) else valor


class UserForm(FlaskForm):
    # Sem campo "nome": o nome completo vem da API de autenticação (AD) e é
    # gravado automaticamente no primeiro login do utilizador.
    username = StringField(
        "Nome de utilizador (nº de colaborador)",
        filters=[_normalizar_username],
        validators=[
            DataRequired(message="Indique o nome de utilizador."),
            Regexp(
                r"^[A-Za-z]{1,2}\d{4,8}$",
                message="Formato inválido (ex.: A272754).",
            ),
            Length(max=20),
        ],
    )
    perfil = SelectField(
        "Perfil",
        choices=[(k, v) for k, v in PERFIS_LABEL.items()],
        validators=[DataRequired()],
    )
    # Palavra-passe local — só utilizada quando AUTH_MODE=local (desenvolvimento).
    # Em produção (AUTH_MODE=ldap) a autenticação é feita no Active Directory.
    password = PasswordField(
        "Palavra-passe",
        validators=[Optional(), Length(min=8, message="Mínimo de 8 caracteres.")],
    )
    password_confirm = PasswordField(
        "Confirmar palavra-passe",
        validators=[EqualTo("password", message="As palavras-passe não coincidem.")],
    )
    ativo = BooleanField("Utilizador ativo", default=True)
    submit = SubmitField("Guardar")

    def __init__(self, utilizador_original=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.utilizador_original = utilizador_original

    def validate_username(self, field):
        username_normalizado = (field.data or "").strip().upper()
        if _mongo_users_ativo():
            from app.repositories.users import UserRepository

            id_original = self.utilizador_original.id if self.utilizador_original else None
            if not UserRepository().username_disponivel(username_normalizado, excepto_id=id_original):
                raise ValidationError("Já existe um utilizador com este nome de utilizador.")
            return
        existente = User.query.filter_by(username=username_normalizado).first()
        if existente and (
            self.utilizador_original is None or existente.id != self.utilizador_original.id
        ):
            raise ValidationError("Já existe um utilizador com este nome de utilizador.")


class ConfiguracaoForm(FlaskForm):
    nome_instituicao = StringField(
        "Instituição", validators=[DataRequired(), Length(max=200)]
    )
    direcao = StringField("Direção / Unidade", validators=[DataRequired(), Length(max=200)])
    morada = StringField("Morada", validators=[Optional(), Length(max=255)])
    contacto = StringField("Contacto", validators=[Optional(), Length(max=80)])
    email_contacto = StringField("E-mail de contacto", validators=[Optional(), Email(), Length(max=150)])
    rodape_pdf = StringField("Rodapé do PDF", validators=[Optional(), Length(max=255)])
    origem_de = StringField("De (unidade)", validators=[DataRequired(), Length(max=80)])
    origem_local = StringField("De (origem / local)", validators=[DataRequired(), Length(max=120)])
    local_emissao = StringField("Local de emissão", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Guardar configurações")
