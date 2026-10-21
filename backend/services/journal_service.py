import json
import mimetypes
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from backend.core.config import config
from backend.db.schema import Decision, PieceJointe, These, Valeur
from backend.models.journal import DecisionEcriture, DecisionRead, PieceRead, TheseEcriture, TheseRead

TAILLE_MAX = 150 * 1024 * 1024    # un document d'enregistrement universel depasse souvent 50 Mo


def dossier_pieces() -> Path:
    """Les fichiers vivent a cote de la base : sauvegardes et deplacements restent coherents."""
    dossier = Path(config.DB_NAME).resolve().parent / "pieces"
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


class JournalService:
    def __init__(self, session: Session):
        self._db = session

    # ── These ──
    def these(self, valeur_id: int) -> TheseRead:
        self._valeur(valeur_id)
        t = self._db.exec(select(These).where(These.valeur_id == valeur_id)).first()
        if not t:
            return TheseRead()
        donnees = t.model_dump(exclude={"id", "valeur_id", "checklist"})
        return TheseRead(**donnees, checklist=json.loads(t.checklist or "{}"))

    def ecrire_these(self, valeur_id: int, data: TheseEcriture) -> TheseRead:
        self._valeur(valeur_id)
        t = self._db.exec(select(These).where(These.valeur_id == valeur_id)).first() or These(valeur_id=valeur_id)
        for cle, v in data.model_dump(exclude={"checklist"}).items():
            setattr(t, cle, v.strip() or None if isinstance(v, str) else v)
        t.checklist = json.dumps(data.checklist, ensure_ascii=False)
        t.maj_le = datetime.now(UTC)
        self._db.add(t)
        self._db.commit()
        return self.these(valeur_id)

    # ── Decisions ──
    def decisions(self, valeur_id: int) -> list[DecisionRead]:
        self._valeur(valeur_id)
        lignes = self._db.exec(select(Decision).where(Decision.valeur_id == valeur_id)
                               .order_by(Decision.jour.desc(), Decision.id.desc()))
        return [DecisionRead.model_validate(d) for d in lignes]

    def ecrire_decision(self, valeur_id: int, data: DecisionEcriture, decision_id: int | None = None) -> DecisionRead:
        self._valeur(valeur_id)
        d = self._decision(valeur_id, decision_id) if decision_id else Decision(valeur_id=valeur_id, **data.model_dump())
        for cle, v in data.model_dump().items():
            setattr(d, cle, v)
        self._db.add(d)
        self._db.commit()
        self._db.refresh(d)
        return DecisionRead.model_validate(d)

    def supprimer_decision(self, valeur_id: int, decision_id: int) -> None:
        self._db.delete(self._decision(valeur_id, decision_id))
        self._db.commit()

    # ── Pieces jointes ──
    def pieces(self, valeur_id: int) -> list[PieceRead]:
        self._valeur(valeur_id)
        lignes = self._db.exec(select(PieceJointe).where(PieceJointe.valeur_id == valeur_id)
                               .order_by(PieceJointe.created_at.desc()))
        return [PieceRead.model_validate(p) for p in lignes]

    async def ajouter_piece(self, valeur_id: int, fichier: UploadFile) -> PieceRead:
        self._valeur(valeur_id)
        contenu = await fichier.read()
        if len(contenu) > TAILLE_MAX:
            raise HTTPException(413, "Fichier trop volumineux (150 Mo maximum).")
        nom = Path(fichier.filename or "document").name
        disque = f"{uuid.uuid4().hex}{Path(nom).suffix.lower()[:10]}"
        (dossier_pieces() / disque).write_bytes(contenu)
        piece = PieceJointe(valeur_id=valeur_id, nom=nom, fichier=disque, taille=len(contenu),
                            type_mime=fichier.content_type or mimetypes.guess_type(nom)[0] or "application/octet-stream")
        self._db.add(piece)
        self._db.commit()
        self._db.refresh(piece)
        return PieceRead.model_validate(piece)

    def piece(self, valeur_id: int, piece_id: int) -> tuple[Path, PieceJointe]:
        p = self._db.get(PieceJointe, piece_id)
        if not p or p.valeur_id != valeur_id:
            raise HTTPException(404, "Document introuvable.")
        chemin = dossier_pieces() / p.fichier
        if not chemin.exists():
            raise HTTPException(410, "Le fichier a disparu du disque.")
        return chemin, p

    def supprimer_piece(self, valeur_id: int, piece_id: int) -> None:
        chemin, p = self.piece(valeur_id, piece_id)
        chemin.unlink(missing_ok=True)
        self._db.delete(p)
        self._db.commit()

    def _decision(self, valeur_id: int, decision_id: int) -> Decision:
        d = self._db.get(Decision, decision_id)
        if not d or d.valeur_id != valeur_id:
            raise HTTPException(404, "Décision introuvable.")
        return d

    def _valeur(self, valeur_id: int) -> Valeur:
        valeur = self._db.get(Valeur, valeur_id)
        if not valeur:
            raise HTTPException(404, "Valeur introuvable.")
        return valeur
