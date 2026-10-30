// @ts-check

/** Etoile d'une valeur favorite. Dans une ligne de tableau, ne doit pas ouvrir la fiche. */
export default function Favori({ actif, onBasculer }) {
  const libelle = actif ? 'Retirer des favoris' : 'Ajouter aux favoris'
  return (
    <button type="button" className={`favori${actif ? ' actif' : ''}`} title={libelle} aria-label={libelle} aria-pressed={!!actif}
            onClick={e => { e.stopPropagation(); onBasculer(!actif) }}>
      {actif ? '★' : '☆'}
    </button>
  )
}
