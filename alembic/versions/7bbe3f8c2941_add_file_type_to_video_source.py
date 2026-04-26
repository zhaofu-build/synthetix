"""add file_type to video_source

Revision ID: 7bbe3f8c2941
Revises: b03b3aa5180c
Create Date: 2026-04-26 14:01:36.140769

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7bbe3f8c2941'
down_revision = 'b03b3aa5180c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('video_source', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_type', sa.String(length=20), nullable=True, comment='素材类型'))


def downgrade() -> None:
    with op.batch_alter_table('video_source', schema=None) as batch_op:
        batch_op.drop_column('file_type')
