"""add revisao_tecnico_id

Revision ID: c0d1e2f3a4b5
Revises: ab12cd34ef56
Create Date: 2026-08-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c0d1e2f3a4b5"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("notas_saida", schema=None) as batch_op:
        batch_op.add_column(sa.Column("revisao_tecnico_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notas_saida_revisao_tecnico_id_users",
            "users",
            ["revisao_tecnico_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("notas_saida", schema=None) as batch_op:
        batch_op.drop_constraint("fk_notas_saida_revisao_tecnico_id_users", type_="foreignkey")
        batch_op.drop_column("revisao_tecnico_id")
