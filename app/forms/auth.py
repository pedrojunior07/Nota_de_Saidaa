"""Formulário de autenticação."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Regexp


def _normalizar_username(valor):
    return valor.strip().upper() if isinstance(valor, str) else valor


class LoginForm(FlaskForm):
    username = StringField(
        "Utilizador",
        filters=[_normalizar_username],
        validators=[
            DataRequired(message="Indique o nome de utilizador."),
            Regexp(
                r"^[A-Za-z]{1,2}\d{4,8}$",
                message="Formato inválido. Use o seu nº de colaborador (ex.: A272754).",
            ),
        ],
        render_kw={
            "placeholder": "A272754",
            "autocomplete": "username",
            "autocapitalize": "characters",
            "spellcheck": "false",
            "maxlength": 10,
        },
    )
    password = PasswordField(
        "Palavra-passe do computador",
        validators=[DataRequired(message="Indique a palavra-passe.")],
        render_kw={"placeholder": "••••••••", "autocomplete": "current-password"},
    )
    lembrar = BooleanField("Manter sessão iniciada")
    submit = SubmitField("Iniciar sessão")
