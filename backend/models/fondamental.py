from typing import Optional

from pydantic import BaseModel, create_model

from backend.db.champs import CLES

# Un champ facultatif par poste de champs.py : seuls les postes envoyes sont modifies.
FondamentalEcriture = create_model(  # type: ignore[call-overload]
    "FondamentalEcriture", __base__=BaseModel, **{cle: (Optional[float], None) for cle in CLES},
)


class FondamentalRead(FondamentalEcriture):  # type: ignore[valid-type, misc]
    annee:   int
    source:  str
    sources: dict[str, str] = {}     # provenance de chaque case
    ajustes: list[str] = []          # postes ramenes a la base d'actions actuelle (divisions)
    per:     Optional[float] = None  # cours moyen de l'annee / BPA
