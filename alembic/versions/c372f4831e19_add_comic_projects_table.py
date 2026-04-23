"""add comic_projects table

Revision ID: c372f4831e19
Revises: 1d44fe6a55ac
Create Date: 2026-04-23 22:05:04.484928

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c372f4831e19'
down_revision = '1d44fe6a55ac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('comic_projects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False, comment='项目名称'),
    sa.Column('description', sa.Text(), nullable=True, comment='项目描述'),
    sa.Column('genre', sa.String(length=50), nullable=True, comment='类型: drama/comedy/action/romance/horror'),
    sa.Column('style', sa.String(length=50), nullable=True, comment='画风: 动漫/写实/水墨/像素/美漫'),
    sa.Column('status', sa.String(length=50), nullable=True, comment='状态: draft/scripting/generating/compositing/completed'),
    sa.Column('script_data', sa.JSON(), nullable=True, comment='完整脚本 JSON'),
    sa.Column('characters', sa.JSON(), nullable=True, comment='角色定义列表'),
    sa.Column('panels', sa.JSON(), nullable=True, comment='分镜列表（含图片/音频路径）'),
    sa.Column('audio_config', sa.JSON(), nullable=True, comment='音频配置'),
    sa.Column('bgm_config', sa.JSON(), nullable=True, comment='BGM 配置 {path, volume, fade_in, fade_out}'),
    sa.Column('current_step', sa.Integer(), nullable=True, comment='当前工作流步骤'),
    sa.Column('output_videos', sa.JSON(), nullable=True, comment='输出视频列表 [{path, created_at}]'),
    sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('comic_projects')
