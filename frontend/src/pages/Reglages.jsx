// @ts-check
import { useEffect, useRef, useState } from 'react'
import Aide from '../components/Aide'
import Partage from '../components/Partage'
import { api } from '../lib/api'

const AUTRE = '__autre'
const REPLIES = ['E-mail des alertes']   // rubriques facultatives : fermees au depart
const COLONNE_DROITE = ['Alertes', 'E-mail des alertes', 'Données']

/** Champ de texte enregistre a la sortie du champ ou sur Entree. Un secret laisse vide reste inchange. */
function Saisie({ r, surEcrire, court = false }) {
  const [texte, setTexte] = useState(r.secret ? '' : r.valeur)
  const fin = () => {
    if (r.secret ? texte : texte !== r.valeur) surEcrire(r.cle, texte)
    if (r.secret) setTexte('')
  }
  return (
    <input id={r.cle} className={`champ${court ? ' court' : ''}`} type={r.secret ? 'password' : 'text'}
           placeholder={r.secret && r.valeur ? 'déjà renseigné' : r.defaut} value={texte} onChange={e => setTexte(e.target.value)}
           onBlur={fin} onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }} />
  )
}

/** Menu deroulant ; avec « Autre… », un petit champ apparait a cote pour une valeur hors de la liste. */
function Menu({ r, options, surEcrire }) {
  const courant = r.valeur || r.defaut
  const connue = options.some(([v]) => v === courant)
  const [libre, setLibre] = useState(r.autre && !connue)
  // Valeur saisie avant l'arrivee des menus : on la montre plutot que de la remplacer en silence.
  const liste = connue || r.autre ? options : [...options, [courant, courant]]
  return (
    <>
      {libre && <Saisie r={r} surEcrire={surEcrire} court />}
      <select id={libre ? undefined : r.cle} className={`champ${libre ? ' court' : ''}`} value={libre ? AUTRE : courant} aria-label={r.libelle}
              onChange={e => {
                const autre = e.target.value === AUTRE
                setLibre(autre)
                if (!autre) surEcrire(r.cle, e.target.value)
              }}>
        {liste.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        {r.autre && <option value={AUTRE}>Autre…</option>}
      </select>
    </>
  )
}

function Ligne({ r, valeurs, modeles, surEcrire }) {
  const options = r.source === 'valeurs' ? valeurs : r.source === 'modeles' ? modeles : r.choix
  return (
    <div className="reglage">
      <label className="reglage-libelle" htmlFor={r.cle}>{r.libelle}<Aide titre={r.libelle} texte={r.aide} /></label>
      <div className="reglage-controle">
        {options.length ? <Menu r={r} options={options} surEcrire={surEcrire} /> : <Saisie r={r} surEcrire={surEcrire} />}
      </div>
    </div>
  )
}

export default function Reglages() {
  const [reglages, setReglages] = useState(null)
  const [valeurs, setValeurs] = useState([])
  const [modeles, setModeles] = useState([['', 'Automatique']])
  const [erreur, setErreur] = useState(null)
  const [enregistre, setEnregistre] = useState(false)
  const minuterie = useRef(null)

  useEffect(() => {
    api.reglages.list().then(setReglages).catch(e => setErreur(e.message))
    // Indice de reference : parmi ce qui est suivi, les indices et les ETF.
    api.valeurs.list().then(l => setValeurs(l.filter(v => v.type === 'indice' || v.type === 'etf')
      .map(v => [v.symbole, v.nom]))).catch(() => {})
    api.assistant.etat().then(e => setModeles([['', 'Automatique'], ...(e.modeles ?? []).map(x => [x.nom, x.nom])])).catch(() => {})
    return () => clearTimeout(minuterie.current)
  }, [])

  const ecrire = async (cle, valeur) => {
    setErreur(null)
    try {
      setReglages(await api.reglages.ecrire(cle, valeur))
      setEnregistre(true)
      clearTimeout(minuterie.current)
      minuterie.current = setTimeout(() => setEnregistre(false), 2000)
    } catch (e) { setErreur(e.message) }
  }

  /** @type {Record<string, any[]>} */
  const groupes = {}
  for (const r of reglages ?? []) (groupes[r.groupe] ??= []).push(r)
  const lignes = g => groupes[g].map(r => <Ligne key={r.cle} r={r} valeurs={valeurs} modeles={modeles} surEcrire={ecrire} />)
  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Réglages</h1>
          <div className="page-sous-titre">Enregistrés dès que vous les changez · <a className="lien-poste" href="/alertes">tester les notifications</a></div>
        </div>
        {enregistre && <span className="positif">Enregistré</span>}
      </div>
      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {reglages === null ? <div className="chargement">Chargement…</div> : (
        // Deux colonnes fixes : une bulle d'aide ou une rubrique depliee ne deplace jamais une carte d'une colonne a l'autre.
        <div className="reglages-grille">
          {[false, true].map(droite => (
            <div key={String(droite)} className="pile" style={{ gap: 16 }}>
              {Object.keys(groupes).filter(g => COLONNE_DROITE.includes(g) === droite).map(g => REPLIES.includes(g) ? (
                <details key={g} className="carte">
                  <summary className="section-titre">{g}<span className="discret">Facultatif ▾</span></summary>
                  {lignes(g)}
                </details>
              ) : (
                <div key={g} className="carte">
                  <div className="section-titre">{g}</div>
                  {lignes(g)}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
      <Partage />
      <p className="discret" style={{ marginTop: 16 }}>
        Version, emplacement des données et diagnostic de dépannage : page <a href="/a-propos">À propos</a>.
      </p>
    </div>
  )
}
