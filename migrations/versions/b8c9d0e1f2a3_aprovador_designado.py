"""aprovador escolhido pelo técnico ao submeter (notas de saída e de entrega)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

_TABELAS = ("notas_saida", "notas_entrega")


def upgrade():
    for tabela in _TABELAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("aprovador_designado_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f"fk_{tabela}_aprovador_designado", "users",
                ["aprovador_designado_id"], ["id"],
            )


def downgrade():
    for tabela in _TABELAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_constraint(f"fk_{tabela}_aprovador_designado", type_="foreignkey")
            batch_op.drop_column("aprovador_designado_id")
