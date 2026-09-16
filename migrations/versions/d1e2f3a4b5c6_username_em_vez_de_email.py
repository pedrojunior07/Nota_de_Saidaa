"""username em vez de email (autenticação por nº de colaborador / AD)

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-08-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=20), nullable=True))

    # Popular username para linhas já existentes (ambientes de desenvolvimento).
    # Em produção a tabela arranca vazia e este passo não faz nada.
    for (user_id,) in bind.execute(sa.text("SELECT id FROM users WHERE username IS NULL")):
        bind.execute(
            sa.text("UPDATE users SET username = :u WHERE id = :id"),
            {"u": f"A{int(user_id):06d}", "id": user_id},
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "username", existing_type=sa.String(length=20), nullable=False
        )
        batch_op.create_index(
            batch_op.f("ix_users_username"), ["username"], unique=True
        )
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=256),
            nullable=True,
        )
        batch_op.drop_index(batch_op.f("ix_users_email"))
        batch_op.drop_column("email")


def downgrade():
    bind = op.get_bind()

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=150), nullable=True))

    for (user_id,) in bind.execute(sa.text("SELECT id FROM users WHERE email IS NULL")):
        bind.execute(
            sa.text("UPDATE users SET email = :e WHERE id = :id"),
            {"e": f"user{user_id}@local", "id": user_id},
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email", existing_type=sa.String(length=150), nullable=False
        )
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=256),
            nullable=False,
        )
        batch_op.drop_index(batch_op.f("ix_users_username"))
        batch_op.drop_column("username")
