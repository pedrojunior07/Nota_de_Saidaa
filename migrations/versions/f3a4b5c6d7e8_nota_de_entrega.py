"""tabelas da Nota de Entrega (notas_entrega, itens_entrega, historico_entrega)

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

_PAPEIS = ("entregue", "recebido", "aprovador", "seguranca")


def _colunas_assinatura():
    cols = []
    for papel in _PAPEIS:
        cols.append(sa.Column(f"assinatura_{papel}_path", sa.String(length=255), nullable=True))
        for eixo in ("x", "y", "w", "h"):
            cols.append(sa.Column(f"assinatura_{papel}_{eixo}", sa.Float(), nullable=True))
    return cols


def upgrade():
    op.create_table(
        "notas_entrega",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero_referencia", sa.String(length=50), nullable=False),
        sa.Column("data_emissao", sa.Date(), nullable=False),
        sa.Column("funcionario", sa.String(length=150), nullable=False),
        sa.Column("email_funcionario", sa.String(length=150), nullable=False),
        sa.Column("departamento", sa.String(length=120), nullable=False),
        sa.Column("motivo", sa.String(length=200), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("criado_por", sa.Integer(), nullable=False),
        sa.Column("aprovado_por", sa.Integer(), nullable=True),
        sa.Column("seguranca_por", sa.Integer(), nullable=True),
        sa.Column("revisao_tecnico_id", sa.Integer(), nullable=True),
        sa.Column("data_aprovacao", sa.DateTime(), nullable=True),
        sa.Column("data_seguranca", sa.DateTime(), nullable=True),
        sa.Column("data_conclusao", sa.DateTime(), nullable=True),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.Column("pdf_path", sa.String(length=255), nullable=True),
        sa.Column("comentario_decisao", sa.Text(), nullable=True),
        sa.Column("origem_local", sa.String(length=120), server_default="Sede IT", nullable=False),
        sa.Column("local_emissao", sa.String(length=80), server_default="Maputo", nullable=False),
        *_colunas_assinatura(),
        sa.ForeignKeyConstraint(["criado_por"], ["users.id"]),
        sa.ForeignKeyConstraint(["aprovado_por"], ["users.id"]),
        sa.ForeignKeyConstraint(["seguranca_por"], ["users.id"]),
        sa.ForeignKeyConstraint(["revisao_tecnico_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notas_entrega", schema=None) as batch:
        batch.create_index("ix_notas_entrega_numero_referencia", ["numero_referencia"], unique=True)
        batch.create_index("ix_notas_entrega_funcionario", ["funcionario"], unique=False)
        batch.create_index("ix_notas_entrega_email_funcionario", ["email_funcionario"], unique=False)
        batch.create_index("ix_notas_entrega_estado", ["estado"], unique=False)

    op.create_table(
        "itens_entrega",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nota_id", sa.Integer(), nullable=False),
        sa.Column("tipo_item", sa.String(length=80), nullable=False),
        sa.Column("destino", sa.String(length=200), nullable=True),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("numero_serie", sa.String(length=100), nullable=True),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["nota_id"], ["notas_entrega.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "historico_entrega",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nota_id", sa.Integer(), nullable=False),
        sa.Column("utilizador", sa.String(length=150), nullable=False),
        sa.Column("acao", sa.String(length=255), nullable=False),
        sa.Column("data_hora", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["nota_id"], ["notas_entrega.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("historico_entrega", schema=None) as batch:
        batch.create_index("ix_historico_entrega_data_hora", ["data_hora"], unique=False)


def downgrade():
    op.drop_table("historico_entrega")
    op.drop_table("itens_entrega")
    with op.batch_alter_table("notas_entrega", schema=None) as batch:
        batch.drop_index("ix_notas_entrega_estado")
        batch.drop_index("ix_notas_entrega_email_funcionario")
        batch.drop_index("ix_notas_entrega_funcionario")
        batch.drop_index("ix_notas_entrega_numero_referencia")
    op.drop_table("notas_entrega")
