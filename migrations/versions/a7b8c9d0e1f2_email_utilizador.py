"""e-mail do utilizador (para notificações)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    # Bases antigas atualizadas pelo ajuste automático do app/__init__.py (e
    # não pela migração d1e2f3a4b5c6) podem ainda ter a coluna "email" do
    # login antigo, NOT NULL e única: nesse caso só a tornamos opcional.
    colunas = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    with op.batch_alter_table("users", schema=None) as batch_op:
        if "email" in colunas:
            batch_op.alter_column("email", existing_type=sa.String(length=150), nullable=True)
        else:
            batch_op.add_column(sa.Column("email", sa.String(length=150), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("email")
