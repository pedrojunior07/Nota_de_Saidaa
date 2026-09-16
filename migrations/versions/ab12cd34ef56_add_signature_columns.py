"""add signature columns

Revision ID: ab12cd34ef56
Revises: ee7cc41d9379
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab12cd34ef56'
down_revision = 'ee7cc41d9379'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assinatura_path', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('assinatura_reutilizavel', sa.Boolean(), server_default=sa.text('0'), nullable=False))

    with op.batch_alter_table('notas_saida', schema=None) as batch_op:
        batch_op.add_column(sa.Column('assinatura_entregue_path', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('assinatura_aprovador_path', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('assinatura_entregue_x', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_entregue_y', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_entregue_w', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_entregue_h', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_aprovador_x', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_aprovador_y', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_aprovador_w', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('assinatura_aprovador_h', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('notas_saida', schema=None) as batch_op:
        batch_op.drop_column('assinatura_aprovador_h')
        batch_op.drop_column('assinatura_aprovador_w')
        batch_op.drop_column('assinatura_aprovador_y')
        batch_op.drop_column('assinatura_aprovador_x')
        batch_op.drop_column('assinatura_entregue_h')
        batch_op.drop_column('assinatura_entregue_w')
        batch_op.drop_column('assinatura_entregue_y')
        batch_op.drop_column('assinatura_entregue_x')
        batch_op.drop_column('assinatura_aprovador_path')
        batch_op.drop_column('assinatura_entregue_path')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('assinatura_reutilizavel')
        batch_op.drop_column('assinatura_path')
