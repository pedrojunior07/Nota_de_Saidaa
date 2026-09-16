"""nota de saída: marca notas registadas a partir de um PDF carregado

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("notas_saida", schema=None) as batch:
        batch.add_column(
            sa.Column("pdf_carregado", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade():
    with op.batch_alter_table("notas_saida", schema=None) as batch:
        batch.drop_column("pdf_carregado")
