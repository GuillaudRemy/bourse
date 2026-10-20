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
    """Donnees annuelles d'une entreprise : de quoi verifier que la pente du cours
    est portee par les benefices, pas par un gonflement du PER.

    `source` : « yahoo », « import » ou « manuel ». Une actualisation Yahoo
    n'ecrase jamais une ligne saisie ou importee a la main.
    """
    __table_args__ = (UniqueConstraint("valeur_id", "annee"),)

    id:     Optional[int] = Field(default=None, primary_key=True)
    annee:  int = Field(index=True)

    bpa:              Optional[float] = None   # benefice par action
    benefice_net:     Optional[float] = None
    chiffre_affaires: Optional[float] = None
    dividende:        Optional[float] = None   # dividende par action verse dans l'annee
    source:           str = "manuel"

    valeur_id: int = Field(
        sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"), index=True, nullable=False),
    )
    valeur: Optional[Valeur] = Relationship(back_populates="fondamentaux")
