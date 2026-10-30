"""valeurs favorites

Revision : 0011
Precedente : 0010
"""
from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('valeur', schema=None) as batch_op:
        batch_op.add_column(sa.Column('favori', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('valeur', schema=None) as batch_op:
        batch_op.drop_column('favori')
