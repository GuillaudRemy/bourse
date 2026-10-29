"""taux sans risque et historique du consensus

Revision : 0008
Precedente : 0007
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tauxsansrisque',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('zone', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('jour', sa.Date(), nullable=False),
        sa.Column('taux', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zone', 'jour'),
    )
    with op.batch_alter_table('tauxsansrisque', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tauxsansrisque_zone'), ['zone'], unique=False)
    op.create_table(
        'consensusprevision',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jour', sa.Date(), nullable=False),
        sa.Column('decalage', sa.Integer(), nullable=False),
        sa.Column('annee', sa.Integer(), nullable=True),
        sa.Column('bpa', sa.Float(), nullable=False),
        sa.Column('bas', sa.Float(), nullable=True),
        sa.Column('haut', sa.Float(), nullable=True),
        sa.Column('analystes', sa.Integer(), nullable=True),
        sa.Column('objectif', sa.Float(), nullable=True),
        sa.Column('valeur_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['valeur_id'], ['valeur.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('valeur_id', 'jour', 'decalage'),
    )
    with op.batch_alter_table('consensusprevision', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_consensusprevision_valeur_id'), ['valeur_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('consensusprevision', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_consensusprevision_valeur_id'))
    op.drop_table('consensusprevision')
    with op.batch_alter_table('tauxsansrisque', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tauxsansrisque_zone'))
    op.drop_table('tauxsansrisque')
