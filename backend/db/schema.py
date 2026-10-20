from datetime import UTC, date, datetime
from typing import List, Optional

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

TYPES = ("action", "indice", "etf")
SOURCES = ("yahoo", "import")


class Valeur(SQLModel, table=True):
    """Une valeur suivie : action, indice ou ETF.

    `source` dit d'ou viennent les cours : « yahoo » (telecharges et actualises),
    ou « import » (fichier televerse a la main, quand aucune API ne couvre la valeur).
    """
    id:         Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    symbole: str = Field(unique=True, index=True)   # ticker Yahoo, ou code libre si import
    nom:     str
    type:    str = "action"
    source:  str = "yahoo"
    devise:  Optional[str] = None
    place:   Optional[str] = None
    secteur: Optional[str] = None
    pays:    Optional[str] = None
    # Identifiants pour retrouver les comptes officiels : ISIN -> LEI (ESEF, Europe), CIK (SEC, USA).
    isin:    Optional[str] = Field(default=None, index=True)
    lei:     Optional[str] = None
    cik:     Optional[str] = None
    # Devise des comptes publies, parfois differente de la devise de cotation.
    devise_comptes: Optional[str] = None

    # Vide = debut par defaut selon le type (voir config).
    debut_regression: Optional[date] = None
    # L'utilisateur signale un changement de nature de l'entreprise (3e verification).
    rupture: bool = False
    notes:   Optional[str] = None

    # Dernier instantane des ratios fournis par la source, en JSON.
    infos:  Optional[str] = None
    maj_le: Optional[datetime] = None

    cours: List["Cours"] = Relationship(
        back_populates="valeur",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    fondamentaux: List["Fondamental"] = Relationship(
        back_populates="valeur",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    divisions: List["Division"] = Relationship(
        back_populates="valeur",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Cours(SQLModel, table=True):
    """Une seance. `ajuste` est le cours dividendes reinvestis (rendement total) :
    c'est sur lui que se trace la droite de regression."""
    __table_args__ = (UniqueConstraint("valeur_id", "jour"),)

    id:     Optional[int] = Field(default=None, primary_key=True)
    jour:   date = Field(index=True)

    ouverture: Optional[float] = None
    haut:      Optional[float] = None
    bas:       Optional[float] = None
    cloture:   float
    ajuste:    Optional[float] = None
    volume:    Optional[float] = None

    valeur_id: int = Field(
        sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    valeur: Optional[Valeur] = Relationship(back_populates="cours")


class Fondamental(SQLModel, table=True):
    """Etats financiers d'une annee : compte de resultat, bilan, flux de tresorerie.

    La liste des postes et leur sens sont decrits dans `champs.py`. Les montants sont
    stockes tels que publies ; les postes par action sont ajustes des divisions
    d'actions au moment de l'analyse.

    `sources` (JSON) donne la provenance de chaque case : {"bpa": "esef", "capex": "yahoo"…}.
    Une case n'est remplacee que par une source au moins aussi fiable (voir champs.PRIORITE) :
    une actualisation n'ecrase jamais une saisie ou un import manuel.
    """
    __table_args__ = (UniqueConstraint("valeur_id", "annee"),)

    id:     Optional[int] = Field(default=None, primary_key=True)
    annee:  int = Field(index=True)

    # Compte de resultat
    chiffre_affaires: Optional[float] = None
    marge_brute:      Optional[float] = None
    frais_generaux:   Optional[float] = None
    ebitda:           Optional[float] = None
    amortissements:   Optional[float] = None
    ebit:             Optional[float] = None
    charges_interets: Optional[float] = None
    benefice_net:     Optional[float] = None
    # Par action
    bpa:              Optional[float] = None
    dividende:        Optional[float] = None
    nombre_actions:   Optional[float] = None
    # Bilan
    total_actif:                 Optional[float] = None
    actifs_courants:             Optional[float] = None
    tresorerie:                  Optional[float] = None
    creances_clients:            Optional[float] = None
    immobilisations_corporelles: Optional[float] = None
    goodwill:                    Optional[float] = None
    passifs_courants:            Optional[float] = None
    total_passif:                Optional[float] = None
    dette_financiere:            Optional[float] = None
    dette_long_terme:            Optional[float] = None
    capitaux_propres:            Optional[float] = None
    resultats_non_distribues:    Optional[float] = None
    # Flux de tresorerie
    flux_operationnel: Optional[float] = None
    capex:             Optional[float] = None
    dividendes_verses: Optional[float] = None
    rachats_actions:   Optional[float] = None

    source:  str = "manuel"            # source principale de la ligne (la plus fiable presente)
    sources: Optional[str] = None      # provenance case par case, en JSON

    valeur_id: int = Field(
        sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    valeur: Optional[Valeur] = Relationship(back_populates="fondamentaux")


class Division(SQLModel, table=True):
    """Division d'actions (ou attribution gratuite) : `ratio` = nouvelles actions pour une ancienne.

    Air Liquide, 1 action gratuite pour 10 : ratio 1,1. Sert a rendre comparables les BPA
    publies avant et apres la division."""
    __table_args__ = (UniqueConstraint("valeur_id", "jour"),)

    id:    Optional[int] = Field(default=None, primary_key=True)
    jour:  date
    ratio: float

    valeur_id: int = Field(
        sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    valeur: Optional[Valeur] = Relationship(back_populates="divisions")


class TauxChange(SQLModel, table=True):
    """Taux de reference de la BCE : `taux` unites de `devise` pour 1 euro."""
    __table_args__ = (UniqueConstraint("devise", "jour"),)

    id:     Optional[int] = Field(default=None, primary_key=True)
    devise: str = Field(index=True)
    jour:   date = Field(index=True)
    taux:   float


class Reglage(SQLModel, table=True):
    """Reglages de l'application, modifiables depuis l'interface (cle -> valeur texte)."""
    cle:    str = Field(primary_key=True)
    valeur: Optional[str] = None
