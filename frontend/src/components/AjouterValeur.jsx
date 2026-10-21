import { useEffect, useState } from 'react'
import Modale from './Modale'
import { api } from '../lib/api'
import { TYPES } from '../lib/zones'

/** Ajout d'une valeur : recherche chez Yahoo, ou creation vide pour un import de fichier. */
export default function AjouterValeur({ onFermer, onAjoutee, texteInitial = '' }) {
  const [mode, setMode] = useState('yahoo')
  const [texte, setTexte] = useState(texteInitial)
  const [resultats, setResultats] = useState([])
  const [recherche, setRecherche] = useState(false)
  const [ajout, setAjout] = useState(null)        // symbole en cours d'ajout
  const [erreur, setErreur] = useState(null)
  const [manuel, setManuel] = useState({ symbole: '', nom: '', type: 'action', devise: 'EUR' })

  // Recherche a la frappe, apres une courte pause.
  useEffect(() => {
    if (mode !== 'yahoo' || texte.trim().length < 2) { setResultats([]); return }
    const minuterie = setTimeout(async () => {
      setRecherche(true); setErreur(null)
      try { setResultats(await api.valeurs.recherche(texte.trim())) }
      catch (e) { setErreur(e.message) }
      finally { setRecherche(false) }
    }, 350)
    return () => clearTimeout(minuterie)
  }, [texte, mode])

  const ajouterYahoo = async symbole => {
    setAjout(symbole); setErreur(null)
    const isin = /^[A-Z]{2}[A-Z0-9]{9}\d$/.test(texte.trim().toUpperCase()) ? texte.trim().toUpperCase() : undefined
    try { onAjoutee(await api.valeurs.create({ symbole, source: 'yahoo', isin })) }
    catch (e) { setErreur(e.message) }
    finally { setAjout(null) }
  }

  const ajouterManuel = async e => {
    e.preventDefault()
    setAjout(manuel.symbole); setErreur(null)
    try { onAjoutee(await api.valeurs.create({ ...manuel, source: 'import' }), true) }
    catch (e) { setErreur(e.message) }
    finally { setAjout(null) }
  }

  return (
    <Modale titre="Ajouter une valeur" onFermer={onFermer}>
      <div className="segments">
        <button className={`segment${mode === 'yahoo' ? ' actif' : ''}`} onClick={() => setMode('yahoo')}>
          Yahoo Finance
        </button>
        <button className={`segment${mode === 'import' ? ' actif' : ''}`} onClick={() => setMode('import')}>
          Données importées
        </button>
      </div>

      {mode === 'yahoo' ? (
        <>
          <div className="champ-groupe">
            <label className="champ-label">Nom, symbole ou ISIN</label>
            <input
              className="champ" autoFocus value={texte} placeholder="air liquide, AAPL, CAC 40, ^GSPC…"
              onChange={e => setTexte(e.target.value)}
              onKeyDown={e => {
                // Entree sur un symbole exact : ajout direct, sans passer par la liste.
                if (e.key === 'Enter' && texte.trim() && !resultats.length) ajouterYahoo(texte.trim())
              }}
            />
            <span className="discret">
              Données gratuites, sans clé : cours quotidiens depuis l'introduction en bourse,
              dividendes, et comptes des 4–5 dernières années.
            </span>
          </div>
          {recherche && <div className="discret">Recherche…</div>}
          <div className="pile" style={{ gap: 6 }}>
            {resultats.map(r => (
              <button key={r.symbole} className="resultat" disabled={!!ajout} onClick={() => ajouterYahoo(r.symbole)}>
                <span>
                  <div className="valeur-nom">{r.nom}</div>
                  <div className="valeur-symbole">{r.symbole} · {r.place}{r.secteur ? ` · ${r.secteur}` : ''}</div>
                </span>
                <span className="etiquette">{ajout === r.symbole ? 'Téléchargement…' : TYPES[r.type]}</span>
              </button>
            ))}
          </div>
        </>
      ) : (
        <form className="pile" onSubmit={ajouterManuel}>
          <span className="discret">
            Pour une valeur qu'aucune API ne couvre : créez-la ici, puis téléversez ses cours
            (CSV) depuis l'onglet « Données » de sa fiche.
          </span>
          <div className="champ-groupe">
            <label className="champ-label">Code (unique)</label>
            <input className="champ champ-mono" required value={manuel.symbole}
                   onChange={e => setManuel({ ...manuel, symbole: e.target.value })} />
          </div>
          <div className="champ-groupe">
            <label className="champ-label">Nom</label>
            <input className="champ" value={manuel.nom} onChange={e => setManuel({ ...manuel, nom: e.target.value })} />
          </div>
          <div className="rangee">
            <div className="champ-groupe" style={{ flex: 1 }}>
              <label className="champ-label">Type</label>
              <select className="champ" value={manuel.type} onChange={e => setManuel({ ...manuel, type: e.target.value })}>
                {Object.entries(TYPES).map(([cle, libelle]) => <option key={cle} value={cle}>{libelle}</option>)}
              </select>
            </div>
            <div className="champ-groupe" style={{ width: 110 }}>
              <label className="champ-label">Devise</label>
              <input className="champ" value={manuel.devise} onChange={e => setManuel({ ...manuel, devise: e.target.value })} />
            </div>
          </div>
          <button className="btn btn-primaire" disabled={!!ajout || !manuel.symbole.trim()}>Créer la valeur</button>
        </form>
      )}

      {erreur && <div className="erreur">{erreur}</div>}
    </Modale>
  )
}
