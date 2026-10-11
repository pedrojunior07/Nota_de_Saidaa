"""devoluções de equipamento (um registo por item devolvido)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "devolucoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nota_tipo", sa.String(length=10), nullable=False),
        sa.Column("nota_id", sa.String(length=40), nullable=False),
        sa.Column("item_id", sa.String(length=40), nullable=False),
        sa.Column("registo_id", sa.String(length=40), nullable=False),
        sa.Column("data", sa.DateTime(), nullable=False),
        sa.Column("registado_por_id", sa.String(length=40), nullable=True),
        sa.Column("registado_por_nome", sa.String(length=150), nullable=True),
        sa.Column("estado_equipamento", sa.String(length=30), nullable=True),
        sa.Column("motivo", sa.String(length=80), nullable=True),
        sa.Column("observacao", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_devolucoes_nota", "devolucoes", ["nota_tipo", "nota_id"])
    op.create_index("ix_devolucoes_registo_id", "devolucoes", ["registo_id"])


def downgrade():
    op.drop_index("ix_devolucoes_registo_id", table_name="devolucoes")
    op.drop_index("ix_devolucoes_nota", table_name="devolucoes")
    op.drop_table("devolucoes")
