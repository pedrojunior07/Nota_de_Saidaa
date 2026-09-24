"""nome do utilizador passa a ser opcional (preenchido no login via API)

O administrador deixa de escrever o nome ao criar um utilizador: o nome
completo vem do endpoint de autenticação (firstName/lastName) e é gravado
no primeiro login. Até lá a coluna fica NULL.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "nome", existing_type=sa.String(length=150), nullable=True
        )


def downgrade():
    # Repor NOT NULL exige um valor: usa o nº de colaborador onde faltar o nome.
    op.execute("UPDATE users SET nome = username WHERE nome IS NULL OR nome = ''")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "nome", existing_type=sa.String(length=150), nullable=False
        )
