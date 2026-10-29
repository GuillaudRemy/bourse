// @ts-check
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'

const TYPES = { DocumentReference: 'document de référence', DocumentEnregistrementUniversel: 'document d’enregistrement universel' }

/** Rapports annuels archives par l'AMF (societes cotees a Paris, depuis 2005 environ) : la source des comptes
 *  d'avant 2020, qu'ESEF ne couvre pas. Chaque lecture donne une proposition a relire. */
export default function ArchivesAmf({ valeurId, annees, onProposition }) {
  const [d, setD] = useState(null)
  const [lecture, setLecture] = useState(null)
  const [erreur, setErreur] = useState(null)
  useEffect(() => { api.amf.documents(valeurId).then(setD).catch(e => setErreur(e.message)) }, [valeurId])
  if (d && !d.couvert) return null

  const lire = async annee => {
    setLecture(annee); setErreur(null)
    try { onProposition(await api.amf.lire(valeurId, annee)); setD({ ...d, documents: d.documents.map(x => x.annee === annee ? { ...x, range: true } : x) }) }
    catch (e) { setErreur(e.message) }
    finally { setLecture(null) }
  }
  const connues = new Set(annees)

  return (
    <div className="carte">
      <div className="section-titre">Rapports annuels archivés (AMF)</div>
      <div className="carte-corps pile" style={{ gap: 10 }}>
        <span className="discret" style={{ fontSize: 12.5 }}>
          Les comptes d'avant 2020 : chaque rapport donne les chiffres clés de 3 à 5 exercices. Lecture assistée, à relire
          avant enregistrement (jusqu'à une minute par document). Le PDF est rangé dans le journal, où l'assistant peut aussi le lire.
        </span>
        {erreur && <div className="erreur">{erreur}</div>}
        {!d ? <div className="discret">Recherche à l'AMF…</div> : !d.documents.length ? <div className="discret">Aucun rapport trouvé à l'AMF pour cette société.</div> : (
          <div className="rangee" style={{ flexWrap: 'wrap', gap: 6 }}>
            {d.documents.map(x => (
              <button key={x.annee} className={`btn btn-mini${connues.has(x.annee) ? ' btn-fantome' : ''}`} disabled={lecture !== null}
                      title={`${TYPES[x.type] ?? x.type} publié le ${x.date}${connues.has(x.annee) ? ' · exercice déjà présent dans les comptes' : ''}${x.range ? ' · déjà au journal' : ''}`}
                      onClick={() => lire(x.annee)}>
                {lecture === x.annee ? 'Lecture…' : x.annee}{x.range ? ' ✓' : ''}
              </button>
            ))}
          </div>
        )}
        {lecture !== null && <div className="discret">Téléchargement et lecture du rapport {lecture}…</div>}
      </div>
    </div>
  )
}
