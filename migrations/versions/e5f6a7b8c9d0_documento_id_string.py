"""campos dinamicos: documento_id passa a String (suporta ids do Mongo)

A coluna era Integer, assumindo sempre o id auto-incremental do
SQLAlchemy. Uma nota gravada em MongoDB tem um ObjectId em hexadecimal
(24 caracteres, ex.: "6ab02bfa545c27b7436405a3") como id — nunca cabe
numa coluna Integer, e falharia com um erro de tipo em bases de dados
estritas como o PostgreSQL (o SQLite tolera por tipagem dinâmica, mas
não é para confiar nisso em produção).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("valores_campo_dinamico", schema=None) as batch:
        batch.alter_column(
            "documento_id",
            existing_type=sa.Integer(),
            type_=sa.String(length=50),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table("valores_campo_dinamico", schema=None) as batch:
        batch.alter_column(
            "documento_id",
            existing_type=sa.String(length=50),
            type_=sa.Integer(),
            existing_nullable=False,
        )
