"""add_plan_versions_subtitle_data_proxy_dir

Revision ID: 657a9befd12f
Revises: ee4eee023134
Create Date: 2026-04-25 21:40:29.039743

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '657a9befd12f'
down_revision = 'ee4eee023134'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_versions', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        batch_op.drop_column('plan_versions')
