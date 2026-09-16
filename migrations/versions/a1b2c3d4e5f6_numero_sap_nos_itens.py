"""adiciona numero_sap aos itens (nota de saida e nota de entrega)

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-09-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("itens_nota", schema=None) as batch:
        batch.add_column(sa.Column("numero_sap", sa.String(length=100), nullable=True))
    with op.batch_alter_table("itens_entrega", schema=None) as batch:
        batch.add_column(sa.Column("numero_sap", sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table("itens_entrega", schema=None) as batch:
        batch.drop_column("numero_sap")
    with op.batch_alter_table("itens_nota", schema=None) as batch:
        batch.drop_column("numero_sap")
