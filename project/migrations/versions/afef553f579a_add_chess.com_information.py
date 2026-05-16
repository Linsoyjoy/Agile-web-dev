"""Added chess.com information

Revision ID: afef553f579a
Revises: 3201fd6af61c
Create Date: 2026-05-16 01:30:49.970140

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'afef553f579a'
down_revision = '3201fd6af61c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chesscom_username', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('lichess_username', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('fide_id', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('fide_id')
        batch_op.drop_column('lichess_username')
        batch_op.drop_column('chesscom_username')

    # ### end Alembic commands ###
