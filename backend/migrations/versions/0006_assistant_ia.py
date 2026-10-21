"""assistant ia

Revision : 0006
Precedente : 0005
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'analyseia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('titre', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('modele', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('duree', sa.Float(), nullable=True),
        sa.Column('resultat', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('valeur_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['valeur_id'], ['valeur.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('analyseia', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_analyseia_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_analyseia_valeur_id'), ['valeur_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('analyseia', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_analyseia_valeur_id'))
        batch_op.drop_index(batch_op.f('ix_analyseia_created_at'))
    op.drop_table('analyseia')
