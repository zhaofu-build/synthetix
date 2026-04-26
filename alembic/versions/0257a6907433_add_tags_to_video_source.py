"""add_tags_to_video_source

Revision ID: 0257a6907433
Revises: 657a9befd12f
Create Date: 2026-04-25 22:29:40.864878

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0257a6907433'
down_revision = '657a9befd12f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('video_source', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tags', sa.Text(), nullable=True, comment='标签，逗号分隔'))


def downgrade() -> None:
    with op.batch_alter_table('video_source', schema=None) as batch_op:
        batch_op.drop_column('tags')
