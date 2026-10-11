"""devoluções de notas carregadas: equipamento escrito à mão e marca de completa

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-10-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("devolucoes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo_item", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("descricao", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("numero_serie", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("quantidade", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("completa", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("devolucoes", schema=None) as batch_op:
        for coluna in ("completa", "quantidade", "numero_serie", "descricao", "tipo_item"):
            batch_op.drop_column(coluna)
