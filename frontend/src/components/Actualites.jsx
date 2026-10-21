// @ts-check
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { dateHeure } from '../lib/format'

export default function Actualites({ valeurId }) {
  const [articles, setArticles] = useState(null)
  useEffect(() => { api.actualites(valeurId).then(setArticles).catch(() => setArticles([])) }, [valeurId])
  return (
    <div className="carte">
      <div className="section-titre">Actualités (60 derniers jours)</div>
      {articles === null && <div className="chargement">Chargement…</div>}
      {articles?.length === 0 && <div className="vide">Aucune actualité trouvée.</div>}
      {articles?.map((a, i) => (
        <a key={i} className="article" href={a.lien} target="_blank" rel="noreferrer">
          <div className="article-titre">{a.titre}</div>
          <div className="discret">{a.source}{a.moment ? ` · ${dateHeure(a.moment)}` : ''}</div>
        </a>
      ))}
    </div>
  )
}
