"""add_cascade_deletes_and_indexes

Revision ID: 918e85bc5419
Revises: ac966ac1a3e0
Create Date: 2026-05-10 09:32:04.505328

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '918e85bc5419'
down_revision = 'ac966ac1a3e0'
branch_labels = None
depends_on = None


def _index_exists(bind, index_name):
    result = bind.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=:name"
    ), {"name": index_name}).fetchone()
    return result is not None


def _fk_exists(bind, fk_name):
    # SQLite FK names are stored per-table; check all tables
    result = bind.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )).fetchall()
    for (table_name,) in result:
        fks = bind.execute(sa.text(
            "PRAGMA foreign_key_list(:tbl)"
        ), {"tbl": table_name}).fetchall()
        if any(fk[0] == fk_name for fk in fks):
            return True
    return False


def upgrade() -> None:
    conn = op.get_bind()

    # 清理之前失败迁移残留的临时表
    tmp_tables = conn.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp_%'"
    )).fetchall()
    for (tbl,) in tmp_tables:
        conn.execute(sa.text(f'DROP TABLE IF EXISTS "{tbl}"'))

    # 索引：audio_source
    with op.batch_alter_table('audio_source', schema=None) as batch_op:
        if not _index_exists(conn, 'ix_audio_source_audio_name'):
            batch_op.create_index(batch_op.f('ix_audio_source_audio_name'), ['audio_name'], unique=False)
        if not _index_exists(conn, 'ix_audio_source_seed'):
            batch_op.create_index(batch_op.f('ix_audio_source_seed'), ['seed'], unique=False)

    # 级联删除 + 索引：clip_plan_items.project_id → video_projects.id
    with op.batch_alter_table('clip_plan_items', schema=None) as batch_op:
        if not _index_exists(conn, 'ix_clip_plan_items_project_id'):
            batch_op.create_index(batch_op.f('ix_clip_plan_items_project_id'), ['project_id'], unique=False)
        batch_op.create_foreign_key('fk_clip_plan_items_project_id', 'video_projects', ['project_id'], ['id'], ondelete='CASCADE')

    # 级联删除 + 索引：comic_projects
    with op.batch_alter_table('comic_projects', schema=None) as batch_op:
        if not _index_exists(conn, 'ix_comic_projects_series_id'):
            batch_op.create_index(batch_op.f('ix_comic_projects_series_id'), ['series_id'], unique=False)
        if not _index_exists(conn, 'ix_comic_projects_status'):
            batch_op.create_index(batch_op.f('ix_comic_projects_status'), ['status'], unique=False)
        batch_op.create_foreign_key('fk_comic_projects_series_id', 'comic_series', ['series_id'], ['id'], ondelete='SET NULL')

    # 索引：dialog_sessions
    with op.batch_alter_table('dialog_sessions', schema=None) as batch_op:
        if not _index_exists(conn, 'ix_dialog_sessions_current_video_id'):
            batch_op.create_index(batch_op.f('ix_dialog_sessions_current_video_id'), ['current_video_id'], unique=False)
        if not _index_exists(conn, 'ix_dialog_sessions_status'):
            batch_op.create_index(batch_op.f('ix_dialog_sessions_status'), ['status'], unique=False)

    # 索引：video_projects
    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        if not _index_exists(conn, 'ix_video_projects_mode'):
            batch_op.create_index(batch_op.f('ix_video_projects_mode'), ['mode'], unique=False)

    # 级联删除：video_shots.video_id → video_source.id
    with op.batch_alter_table('video_shots', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_video_shots_video_id', 'video_source', ['video_id'], ['id'], ondelete='CASCADE')

    # 索引：video_source
    with op.batch_alter_table('video_source', schema=None) as batch_op:
        if not _index_exists(conn, 'ix_video_source_file_type'):
            batch_op.create_index(batch_op.f('ix_video_source_file_type'), ['file_type'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table('video_source', schema=None) as batch_op:
        if _index_exists(conn, 'ix_video_source_file_type'):
            batch_op.drop_index(batch_op.f('ix_video_source_file_type'))

    with op.batch_alter_table('video_shots', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_video_shots_video_id', 'video_source', ['video_id'], ['id'])

    with op.batch_alter_table('video_projects', schema=None) as batch_op:
        if _index_exists(conn, 'ix_video_projects_mode'):
            batch_op.drop_index(batch_op.f('ix_video_projects_mode'))

    with op.batch_alter_table('dialog_sessions', schema=None) as batch_op:
        if _index_exists(conn, 'ix_dialog_sessions_status'):
            batch_op.drop_index(batch_op.f('ix_dialog_sessions_status'))
        if _index_exists(conn, 'ix_dialog_sessions_current_video_id'):
            batch_op.drop_index(batch_op.f('ix_dialog_sessions_current_video_id'))

    with op.batch_alter_table('comic_projects', schema=None) as batch_op:
        if _index_exists(conn, 'ix_comic_projects_status'):
            batch_op.drop_index(batch_op.f('ix_comic_projects_status'))
        if _index_exists(conn, 'ix_comic_projects_series_id'):
            batch_op.drop_index(batch_op.f('ix_comic_projects_series_id'))

    with op.batch_alter_table('clip_plan_items', schema=None) as batch_op:
        if _index_exists(conn, 'ix_clip_plan_items_project_id'):
            batch_op.drop_index(batch_op.f('ix_clip_plan_items_project_id'))

    with op.batch_alter_table('audio_source', schema=None) as batch_op:
        if _index_exists(conn, 'ix_audio_source_seed'):
            batch_op.drop_index(batch_op.f('ix_audio_source_seed'))
        if _index_exists(conn, 'ix_audio_source_audio_name'):
            batch_op.drop_index(batch_op.f('ix_audio_source_audio_name'))
