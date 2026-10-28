"""actualisation legere

Revision : 0007
Precedente : 0006
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('valeur', schema=None) as batch_op:
        batch_op.add_column(sa.Column('complet_le', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('valeur', schema=None) as batch_op:
        batch_op.drop_column('complet_le')
