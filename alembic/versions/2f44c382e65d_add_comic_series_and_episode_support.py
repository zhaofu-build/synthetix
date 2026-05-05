"""add comic series and episode support

Revision ID: 2f44c382e65d
Revises: 864abee6ac99
Create Date: 2026-05-05 10:38:03.216128

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f44c382e65d'
down_revision = '864abee6ac99'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('comic_series',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False, comment='系列名称'),
    sa.Column('description', sa.Text(), nullable=True, comment='系列描述'),
    sa.Column('style', sa.String(length=50), nullable=True, comment='画风'),
    sa.Column('genre', sa.String(length=50), nullable=True, comment='类型'),
    sa.Column('characters', sa.JSON(), nullable=True, comment='全局角色列表'),
    sa.Column('bgm_config', sa.JSON(), nullable=True, comment='默认 BGM 配置'),
    sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
    sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('comic_projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('series_id', sa.Integer(), nullable=True, comment='所属系列 ID'))
        batch_op.add_column(sa.Column('episode_number', sa.Integer(), nullable=True, comment='集数序号'))
        batch_op.add_column(sa.Column('target_duration', sa.Float(), nullable=True, comment='目标时长（秒）'))


def downgrade() -> None:
    with op.batch_alter_table('comic_projects', schema=None) as batch_op:
        batch_op.drop_column('target_duration')
        batch_op.drop_column('episode_number')
        batch_op.drop_column('series_id')

    op.drop_table('comic_series')
