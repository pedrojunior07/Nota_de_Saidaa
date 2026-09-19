"""nota de entrega: marca notas registadas a partir de um PDF carregado

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("notas_entrega", schema=None) as batch:
        batch.add_column(
            sa.Column("pdf_carregado", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade():
    with op.batch_alter_table("notas_entrega", schema=None) as batch:
        batch.drop_column("pdf_carregado")
