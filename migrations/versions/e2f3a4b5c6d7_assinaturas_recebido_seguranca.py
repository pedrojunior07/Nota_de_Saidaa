"""assinaturas «Recebido» e «Segurança» na nota

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

_PATHS = ("assinatura_recebido_path", "assinatura_seguranca_path")
_FLOATS = tuple(
    f"assinatura_{papel}_{eixo}"
    for papel in ("recebido", "seguranca")
    for eixo in ("x", "y", "w", "h")
)


def upgrade():
    with op.batch_alter_table("notas_saida", schema=None) as batch_op:
        for nome in _PATHS:
            batch_op.add_column(sa.Column(nome, sa.String(length=255), nullable=True))
        for nome in _FLOATS:
            batch_op.add_column(sa.Column(nome, sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("notas_saida", schema=None) as batch_op:
        for nome in reversed(_FLOATS):
            batch_op.drop_column(nome)
        for nome in reversed(_PATHS):
            batch_op.drop_column(nome)
