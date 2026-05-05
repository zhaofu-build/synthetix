"""add is_default to audio_source

Revision ID: 864abee6ac99
Revises: fe63bfd176fe
Create Date: 2026-05-04 21:35:30.348199

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '864abee6ac99'
down_revision = 'fe63bfd176fe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('audio_source', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_default', sa.SmallInteger(), nullable=True, comment='是否为默认音色 0:否 1:是'))


def downgrade() -> None:
    with op.batch_alter_table('audio_source', schema=None) as batch_op:
        batch_op.drop_column('is_default')
