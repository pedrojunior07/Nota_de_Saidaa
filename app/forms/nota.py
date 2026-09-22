"""Formulários da Nota de Saída."""

from flask_wtf import FlaskForm
from wtforms import DateField, FileField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp, ValidationError

from app.utils.constants import ESTADOS_LABEL, MOTIVO_OUTRO, MOTIVOS_ATRIBUICAO, EstadoNota


class NotaForm(FlaskForm):
    origem_local = StringField(
        "De (origem)",
        validators=[DataRequired(message="Indique a origem."), Length(max=120)],
        render_kw={"placeholder": "Sede IT"},
    )
    # O e-mail é procurado no diretório da instituição (Active Directory) e o
    # nome do colaborador é derivado automaticamente da parte antes do "@"
    # — ver static/js/destinatario.js e app/services/directory_service.py.
    email_funcionario = StringField(
        "Para (e-mail)",
        validators=[
            DataRequired(message="Indique o e-mail do destinatário."),
            Email(message="E-mail inválido."),
            Length(max=150),
        ],
        render_kw={
            "placeholder": "Pesquisar colaborador — ex.: clementina.elihud@standardbank.co.mz",
        },
    )
    funcionario = StringField(
        "Nome do colaborador",
        validators=[DataRequired(message="Indique o nome do colaborador."), Length(max=150)],
    )
    departamento = StringField(
        "Departamento do colaborador",
        validators=[DataRequired(message="Indique o departamento."), Length(max=120)],
        render_kw={"placeholder": "Ex.: Recursos Humanos"},
    )
    local_emissao = StringField(
        "Local",
        validators=[DataRequired(), Length(max=80)],
        render_kw={"placeholder": "Maputo"},
    )
    data_emissao = DateField(
        "Data",
        validators=[DataRequired(message="Indique a data.")],
        format="%Y-%m-%d",
    )
    numero_referencia = StringField(
        "N.º Remedy",
        validators=[
            DataRequired(message="Indique o número do ticket Remedy."),
            Length(max=50),
            Regexp(
                r"^REQ\d{12}$",
                message="O numero Remedy deve ter o formato REQ000006253074.",
            ),
        ],
        render_kw={"placeholder": "REQ000006253074"},
    )
    motivo = SelectField(
        "Motivo",
        choices=[(m, m) for m in MOTIVOS_ATRIBUICAO],
        validators=[DataRequired()],
    )
    motivo_outro = StringField(
        "Especifique o motivo",
        validators=[Length(max=200)],
        render_kw={"placeholder": "Descreva o motivo"},
    )
    observacao = TextAreaField(
        "Nota",
        validators=[Optional(), Length(max=2000)],
        render_kw={"rows": 2, "placeholder": "Ex.: Projeto de Estágio"},
    )
    guardar = SubmitField("Guardar rascunho", render_kw={"id": "btnGuardar"})
    submeter = SubmitField("Submeter para aprovação", render_kw={"id": "btnSubmeter"})

    def garantir_motivo(self, valor_atual=None):
        """Mantém motivos antigos/personalizados visíveis ao editar notas já existentes."""
        if valor_atual and valor_atual not in dict(self.motivo.choices):
            self.motivo.choices = [(valor_atual, valor_atual)] + list(self.motivo.choices)

    def validate_motivo_outro(self, field):
        if self.motivo.data == MOTIVO_OUTRO and not (field.data or "").strip():
            raise ValidationError("Especifique o motivo.")

    def motivo_efetivo(self):
        """Motivo a gravar: o texto livre quando a opção escolhida é «Outro»."""
        if self.motivo.data == MOTIVO_OUTRO:
            return (self.motivo_outro.data or "").strip() or MOTIVO_OUTRO
        return self.motivo.data


class CarregarNotaForm(FlaskForm):
    """Regista uma Nota de Saída já existente (documento externo, ex.: nota
    antiga digitalizada) diretamente na listagem, sem passar pelo fluxo
    normal de criação/assinaturas."""

    numero_referencia = StringField(
        "Remedy",
        validators=[DataRequired(message="Indique o número Remedy."), Length(max=50)],
        render_kw={"placeholder": "REQ000006253074"},
    )
    funcionario = StringField(
        "Para (nome)",
        validators=[DataRequired(message="Indique o destinatário."), Length(max=150)],
    )
    email_funcionario = StringField(
        "Para (e-mail)",
        validators=[
            DataRequired(message="Indique o e-mail do destinatário."),
            Email(message="E-mail inválido."),
            Length(max=150),
        ],
    )
    origem_local = StringField(
        "Origem",
        validators=[DataRequired(message="Indique a origem."), Length(max=120)],
        render_kw={"placeholder": "Sede IT"},
    )
    data_emissao = DateField(
        "Emissão", validators=[DataRequired(message="Indique a data.")], format="%Y-%m-%d"
    )
    estado = SelectField(
        "Estado",
        choices=list(ESTADOS_LABEL.items()),
        default=EstadoNota.CONCLUIDA.value,
        validators=[DataRequired()],
    )
    ficheiro = FileField("Ficheiro PDF")
    carregar = SubmitField("Carregar nota")


class DecisaoForm(FlaskForm):
    comentario = TextAreaField(
        "Motivo / comentário",
        validators=[Optional(), Length(max=1000)],
        render_kw={"rows": 3, "placeholder": "Obrigatório para devolver ou rejeitar"},
    )
    tecnico_revisao = SelectField(
        "Técnico para revisão",
        coerce=str,
        validators=[Optional()],
        choices=[],
    )
    aprovar = SubmitField("Aprovar", render_kw={"id": "btnAprovar"})
    devolver = SubmitField("Devolver para revisão", render_kw={"id": "btnDevolver"})
    rejeitar = SubmitField("Rejeitar", render_kw={"id": "btnRejeitar"})
