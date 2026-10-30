"""cryptomonnaies en dollars, ETF obligataires ranges dans les ETF

Revision : 0010
Precedente : 0009
"""
from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connexion = op.get_bind()
    connexion.execute(sa.text("UPDATE valeur SET type = 'etf' WHERE type = 'obligation'"))
    # Cours en euros remplaces par ceux en dollars : effaces ici, retelecharges a la prochaine actualisation.
    cryptos = connexion.execute(sa.text("SELECT id, symbole FROM valeur WHERE type = 'crypto' AND symbole LIKE '%-EUR'")).all()
    existants = {s for (s,) in connexion.execute(sa.text("SELECT symbole FROM valeur"))}
    for identifiant, symbole in cryptos:
        nouveau = symbole[:-4] + "-USD"
        if nouveau in existants:          # deja suivie en dollars : on garde les deux, a supprimer a la main
            continue
        connexion.execute(sa.text("UPDATE valeur SET symbole = :s, devise = 'USD', maj_le = NULL, complet_le = NULL "
                                  "WHERE id = :i"), {"s": nouveau, "i": identifiant})
        connexion.execute(sa.text("DELETE FROM cours WHERE valeur_id = :i"), {"i": identifiant})
    if cryptos:                           # l'actualisation du jour a deja pu avoir lieu : on la refera au demarrage
        connexion.execute(sa.text("DELETE FROM reglage WHERE cle = 'derniere_actualisation'"))


def downgrade() -> None:
    pass                                  # conversion definitive : les cours en euros ne sont pas conserves
