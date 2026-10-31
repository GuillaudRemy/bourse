// @ts-check

/** Bouton carre d'actualisation des cours, le meme partout ; la fleche tourne tant que ca actualise. */
export default function BoutonActualiser({ enCours, onClick, disabled = false }) {
  const libelle = enCours ? 'Actualisation en cours…' : 'Actualiser les cours de toutes les valeurs'
  return (
    <button type="button" className="btn btn-icone" onClick={onClick} disabled={enCours || disabled} title={libelle} aria-label={libelle}>
      <svg className={enCours ? 'tourne' : undefined} width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor"
           strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9" />
        <path d="M13.5 1.5v3h-3" />
      </svg>
    </button>
  )
}
