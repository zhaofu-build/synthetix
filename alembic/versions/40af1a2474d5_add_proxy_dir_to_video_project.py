"""add_proxy_dir_to_video_project

Revision ID: 40af1a2474d5
Revises: c372f4831e19
Create Date: 2026-04-25 12:02:49.011623

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '40af1a2474d5'
down_revision = 'c372f4831e19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('proxy_dir', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        batch_op.drop_column('proxy_dir')
