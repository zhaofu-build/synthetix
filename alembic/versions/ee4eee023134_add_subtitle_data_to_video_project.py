"""add_subtitle_data_to_video_project

Revision ID: ee4eee023134
Revises: 40af1a2474d5
Create Date: 2026-04-25 12:25:50.683057

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ee4eee023134'
down_revision = '40af1a2474d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('subtitle_data', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        batch_op.drop_column('subtitle_data')
