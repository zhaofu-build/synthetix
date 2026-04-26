"""add is_temp to video_source

Revision ID: b03b3aa5180c
Revises: 0257a6907433
Create Date: 2026-04-26 13:46:46.947720

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b03b3aa5180c'
down_revision = '0257a6907433'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('video_source', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_temp', sa.Boolean(), nullable=True, comment='是否临时素材'))


def downgrade() -> None:
    with op.batch_alter_table('video_source', schema=None) as batch_op:
        batch_op.drop_column('is_temp')
