"""add video_shots table

Revision ID: fe63bfd176fe
Revises: 48f3f18dbeb2
Create Date: 2026-04-30 10:52:36.639221

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe63bfd176fe'
down_revision = '48f3f18dbeb2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('video_shots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('video_id', sa.Integer(), nullable=False),
    sa.Column('shot_index', sa.Integer(), nullable=True),
    sa.Column('scene_group', sa.Integer(), nullable=True),
    sa.Column('start_time', sa.Float(), nullable=True),
    sa.Column('end_time', sa.Float(), nullable=True),
    sa.Column('keyframe_paths', sa.JSON(), nullable=True),
    sa.Column('subtitle_text', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('index_status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['video_id'], ['video_source.id']),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('video_shots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_video_shots_video_id'), ['video_id'], unique=False)
        batch_op.create_index('ix_video_shots_video_id_status', ['video_id', 'index_status'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('video_shots', schema=None) as batch_op:
        batch_op.drop_index('ix_video_shots_video_id_status')
        batch_op.drop_index(batch_op.f('ix_video_shots_video_id'))
    op.drop_table('video_shots')
