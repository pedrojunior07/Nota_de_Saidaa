"""Formulário do construtor de campos adicionais (Administrador)."""

from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import BooleanField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, Regexp, ValidationError

from app.models.campo_dinamico import TIPOS_CAMPO, CampoDinamico


class CampoDinamicoForm(FlaskForm):
    nome = StringField(
        "Nome interno",
        validators=[
            DataRequired(message="Indique um nome interno."),
            Length(max=80),
            Regexp(
                r"^[a-zA-Z0-9_]+$",
                message="Use apenas letras, números e underscore (ex.: patrimonio_ti).",
            ),
        ],
    )
    rotulo = StringField(
        "Rótulo (o que aparece no formulário)",
        validators=[DataRequired(message="Indique o rótulo."), Length(max=150)],
    )
    tipo = SelectField("Tipo de campo", choices=TIPOS_CAMPO, validators=[DataRequired()])
    opcoes = TextAreaField(
        "Opções (uma por linha — só para «Lista de opções»)",
        validators=[Optional(), Length(max=4000)],
    )
    aplica_saida = BooleanField("Nota de Saída", default=True)
    aplica_entrega = BooleanField("Nota de Entrega", default=True)
    obrigatorio = BooleanField("Obrigatório")
    ativo = BooleanField("Ativo", default=True)
    ordem = IntegerField("Ordem de exibição", default=0, validators=[Optional()])
    guardar = SubmitField("Guardar")

    def __init__(self, *args, campo_original=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._campo_original = campo_original

    def validate_nome(self, field):
        consulta = CampoDinamico.query.filter(
            func.lower(CampoDinamico.nome) == field.data.strip().lower()
        )
        if self._campo_original:
            consulta = consulta.filter(CampoDinamico.id != self._campo_original.id)
        if consulta.first():
            raise ValidationError("Já existe um campo com este nome interno.")

    def validate_opcoes(self, field):
        if self.tipo.data == "select" and not (field.data or "").strip():
            raise ValidationError("Indique pelo menos uma opção, uma por linha.")

    def validate_aplica_entrega(self, field):
        if not self.aplica_saida.data and not field.data:
            raise ValidationError("O campo tem de se aplicar pelo menos a um documento.")
