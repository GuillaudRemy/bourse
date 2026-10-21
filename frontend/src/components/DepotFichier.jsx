// @ts-check
import { useRef, useState } from 'react'

/** Zone de depot : glisser-deposer ou clic pour choisir un CSV. */
export default function DepotFichier({ onFichier, libelle = 'Déposez un fichier CSV ici, ou cliquez pour le choisir', occupe, accept = '.csv,.txt,text/csv' }) {
  const entree = useRef(null)
  const [survol, setSurvol] = useState(false)

  const choisir = fichiers => {
    if (fichiers?.[0]) onFichier(fichiers[0])
    if (entree.current) entree.current.value = ''
  }

  return (
    <div
      className={`depot${survol ? ' survol' : ''}`}
      onClick={() => !occupe && entree.current?.click()}
      onDragOver={e => { e.preventDefault(); setSurvol(true) }}
      onDragLeave={() => setSurvol(false)}
      onDrop={e => { e.preventDefault(); setSurvol(false); if (!occupe) choisir(e.dataTransfer.files) }}
    >
      {occupe ? 'Import en cours…' : libelle}
      <input ref={entree} type="file" accept={accept} hidden onChange={e => choisir(e.target.files)} />
    </div>
  )
}
