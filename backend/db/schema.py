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


# ── Journal d'investissement ─────────────────────────────────────────
class These(SQLModel, table=True):
    """La these d'investissement d'une valeur, ecrite AVANT d'acheter (une par valeur)."""
    id:         Optional[int] = Field(default=None, primary_key=True)
    maj_le:     datetime = Field(default_factory=lambda: datetime.now(UTC))

    pourquoi:     Optional[str] = None   # pourquoi cette entreprise
    avantage:     Optional[str] = None   # avantage concurrentiel durable
    risques:      Optional[str] = None
    prix_achat:   Optional[float] = None # prix d'achat vise
    prix_vente:   Optional[float] = None # prix ou conditions de vente
    conditions:   Optional[str] = None   # ce qui invaliderait la these
    checklist:    Optional[str] = None   # JSON {question: "oui"|"non"|"?"}

    valeur_id: int = Field(sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"),
                                            unique=True, nullable=False))


class Decision(SQLModel, table=True):
    """Une decision datee (achat, vente, attente…) et, plus tard, sa relecture."""
    id:         Optional[int] = Field(default=None, primary_key=True)
    jour:       date = Field(index=True)
    type:       str                      # achat · renforcement · allegement · vente · attente
    prix:       Optional[float] = None
    raison:     Optional[str] = None
    relecture:  Optional[str] = None     # ce qu'on en pense apres coup
    verdict:    Optional[str] = None     # bonne · mauvaise · neutre

    valeur_id: int = Field(sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"),
                                            index=True, nullable=False))


class PieceJointe(SQLModel, table=True):
    """Document attache a une valeur (rapport annuel, presentation…) ; le fichier vit sur disque."""
    id:         Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    nom:        str
    fichier:    str                      # nom unique sur le disque
    type_mime:  str
    taille:     int

    valeur_id: int = Field(sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"),
                                            index=True, nullable=False))


# ── Portefeuille ─────────────────────────────────────────────────────
class Compte(SQLModel, table=True):
    """Un compte-titres : PEA, compte-titres ordinaire, assurance-vie…"""
    id:            Optional[int] = Field(default=None, primary_key=True)
    nom:           str
    type:          str = "CTO"           # PEA · PEA-PME · CTO · AV · autre
    ouverture:     Optional[date] = None
    courtier:      Optional[str] = None


class Transaction(SQLModel, table=True):
    """Mouvement d'un compte. Montants en euros ; `quantite` et `prix` dans la devise du titre."""
    id:        Optional[int] = Field(default=None, primary_key=True)
    jour:      date = Field(index=True)
    type:      str                       # achat · vente · dividende · frais · depot · retrait · division
    quantite:  Optional[float] = None
    prix:      Optional[float] = None    # prix unitaire, devise du titre
    frais:     float = 0.0               # en euros
    montant:   Optional[float] = None    # en euros (signe : + entree d'argent, - sortie)
    note:      Optional[str] = None

    compte_id: int = Field(sa_column=Column(Integer, ForeignKey("compte.id", ondelete="CASCADE"),
                                            index=True, nullable=False))
    valeur_id: Optional[int] = Field(default=None, sa_column=Column(
        Integer, ForeignKey("valeur.id", ondelete="SET NULL"), index=True))


# ── Alertes et evenements ────────────────────────────────────────────
class Alerte(SQLModel, table=True):
    """Regle surveillee a chaque actualisation : position dans le couloir, RSI, cours…"""
    id:        Optional[int] = Field(default=None, primary_key=True)
    type:      str                       # sigma_sous · sigma_dessus · rsi_sous · rsi_dessus · cours_sous ·
                                         # cours_dessus · croisement_dore · croisement_mort
    seuil:     Optional[float] = None
    active:    bool = True
    derniere:  Optional[date] = None     # derniere fois declenchee (pas de doublon le meme jour)

    valeur_id: int = Field(sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"),
                                            index=True, nullable=False))


class Declenchement(SQLModel, table=True):
    id:        Optional[int] = Field(default=None, primary_key=True)
    moment:    datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    message:   str
    lu:        bool = False

    alerte_id: Optional[int] = Field(default=None, sa_column=Column(
        Integer, ForeignKey("alerte.id", ondelete="SET NULL"), index=True))
    valeur_id: Optional[int] = Field(default=None, sa_column=Column(
        Integer, ForeignKey("valeur.id", ondelete="CASCADE"), index=True))


class Evenement(SQLModel, table=True):
    """Date a venir ou passee : publication de resultats, detachement ou paiement du dividende."""
    __table_args__ = (UniqueConstraint("valeur_id", "jour", "type"),)

    id:     Optional[int] = Field(default=None, primary_key=True)
    jour:   date = Field(index=True)
    type:   str                          # resultats · detachement · paiement
    detail: Optional[str] = None

    valeur_id: int = Field(sa_column=Column(Integer, ForeignKey("valeur.id", ondelete="CASCADE"),
                                            index=True, nullable=False))
