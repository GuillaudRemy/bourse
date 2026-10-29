"""robustesse de l'actualisation, dividendes, journal des corrections

Revision : 0009
Precedente : 0008
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('valeur', schema=None) as batch_op:
        batch_op.add_column(sa.Column('echecs', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('derniere_erreur', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_table(
        'dividende',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jour', sa.Date(), nullable=False),
        sa.Column('montant', sa.Float(), nullable=False),
        sa.Column('valeur_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['valeur_id'], ['valeur.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('valeur_id', 'jour'),
    )
    with op.batch_alter_table('dividende', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dividende_valeur_id'), ['valeur_id'], unique=False)
    op.create_table(
        'correction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('detail', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('valeur_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['valeur_id'], ['valeur.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('correction', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_correction_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_correction_valeur_id'), ['valeur_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('correction', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_correction_valeur_id'))
        batch_op.drop_index(batch_op.f('ix_correction_created_at'))
    op.drop_table('correction')
    with op.batch_alter_table('dividende', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dividende_valeur_id'))
    op.drop_table('dividende')
    with op.batch_alter_table('valeur', schema=None) as batch_op:
        batch_op.drop_column('derniere_erreur')
        batch_op.drop_column('echecs')
