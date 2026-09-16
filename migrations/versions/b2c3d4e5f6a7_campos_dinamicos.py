"""campos dinâmicos (adicionais) do Administrador e os seus valores por nota

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campos_dinamicos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.Column("rotulo", sa.String(length=150), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("opcoes", sa.Text(), nullable=True),
        sa.Column("aplica_saida", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("aplica_entrega", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("obrigatorio", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_por", sa.Integer(), nullable=True),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["criado_por"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("campos_dinamicos", schema=None) as batch:
        batch.create_index("ix_campos_dinamicos_nome", ["nome"], unique=True)

    op.create_table(
        "valores_campo_dinamico",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campo_id", sa.Integer(), nullable=False),
        sa.Column("documento_tipo", sa.String(length=10), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("valor", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["campo_id"], ["campos_dinamicos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campo_id", "documento_tipo", "documento_id", name="uq_valor_campo_documento"
        ),
    )
    with op.batch_alter_table("valores_campo_dinamico", schema=None) as batch:
        batch.create_index(
            "ix_valores_campo_documento", ["documento_tipo", "documento_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("valores_campo_dinamico", schema=None) as batch:
        batch.drop_index("ix_valores_campo_documento")
    op.drop_table("valores_campo_dinamico")
    with op.batch_alter_table("campos_dinamicos", schema=None) as batch:
        batch.drop_index("ix_campos_dinamicos_nome")
    op.drop_table("campos_dinamicos")
