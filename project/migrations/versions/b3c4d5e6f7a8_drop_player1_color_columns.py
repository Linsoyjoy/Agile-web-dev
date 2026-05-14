"""Drop unused player1_color and player2_color columns from match

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-14 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('match', schema=None) as batch_op:
        batch_op.drop_column('player1_color')
        batch_op.drop_column('player2_color')


def downgrade():
    with op.batch_alter_table('match', schema=None) as batch_op:
        batch_op.add_column(sa.Column('player1_color', sa.String(length=5), nullable=True))
        batch_op.add_column(sa.Column('player2_color', sa.String(length=5), nullable=True))
