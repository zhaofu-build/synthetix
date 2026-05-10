"""add config_store table

Revision ID: ac966ac1a3e0
Revises: a00000000001
Create Date: 2026-05-09 23:10:46.669154

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ac966ac1a3e0'
down_revision = 'a00000000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('config_store',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('key', sa.String(length=255), nullable=False, comment='配置键 (点分隔路径)'),
    sa.Column('value', sa.JSON(), nullable=True, comment='配置值 (JSON)'),
    sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('config_store', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_config_store_key'), ['key'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('config_store', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_config_store_key'))

    op.drop_table('config_store')
