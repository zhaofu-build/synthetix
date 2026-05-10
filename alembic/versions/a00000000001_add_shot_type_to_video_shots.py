"""add shot_type to video_shots

Revision ID: a00000000001
Revises: ee4eee023134
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a00000000001'
down_revision = '2f44c382e65d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('video_shots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shot_type', sa.String(length=20), nullable=True, server_default='unknown'))


def downgrade() -> None:
    with op.batch_alter_table('video_shots', schema=None) as batch_op:
        batch_op.drop_column('shot_type')
