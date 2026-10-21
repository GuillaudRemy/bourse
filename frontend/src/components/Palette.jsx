// @ts-check
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

const PAGES = [
  ['Aujourd’hui', '/accueil'], ['Valeurs', '/valeurs'], ['Screener', '/screener'], ['Comparer', '/comparer'],
  ['Backtest', '/backtest'], ['Portefeuille', '/portefeuille'], ['Calendrier', '/calendrier'], ['Alertes', '/alertes'],
  ['Méthode', '/methode'], ['Glossaire', '/glossaire'], ['Réglages', '/reglages'], ['À propos', '/a-propos'],
]
const sansAccents = t => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Recherche globale : Ctrl+K (ou /) ouvre la palette, Entrée ouvre le premier résultat. */
export default function Palette() {
  const naviguer = useNavigate()
  const [ouverte, setOuverte] = useState(false)
  const [texte, setTexte] = useState('')
  const [valeurs, setValeurs] = useState(null)       // null : pas encore chargees
  const [choix, setChoix] = useState(0)
  const champ = useRef(null)
  const entreeEnAttente = useRef(false)    // Entree tapee avant la fin du chargement des valeurs

  useEffect(() => {
    const charger = () => api.valeurs.list().then(setValeurs).catch(() => setValeurs([]))
    charger()
    const touche = e => {
      const saisie = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)
      if ((e.key === 'k' && (e.ctrlKey || e.metaKey)) || (e.key === '/' && !saisie)) {
        e.preventDefault(); setOuverte(true); setTexte(''); setChoix(0)
        charger()
      }
    }
    const ouvrir = () => touche({ key: 'k', ctrlKey: true, preventDefault() {} })
    window.addEventListener('keydown', touche)
    window.addEventListener('ouvrir-palette', ouvrir)
    return () => { window.removeEventListener('keydown', touche); window.removeEventListener('ouvrir-palette', ouvrir) }
  }, [])

  const resultats = useMemo(() => {
    const t = sansAccents(texte.trim())
    const pages = PAGES.filter(([nom]) => !t || sansAccents(nom).includes(t)).map(([nom, lien]) => ({ nom, lien, type: 'Page' }))
    const vals = (valeurs ?? []).filter(v => !t || sansAccents(`${v.nom} ${v.symbole} ${v.isin ?? ''}`).includes(t))
      .slice(0, 8).map(v => ({ nom: v.nom, detail: v.symbole, lien: `/valeurs/${v.id}`, type: 'Valeur' }))
    const liste = t ? [...vals, ...pages] : [...pages, ...vals]
    // Tant que la liste n'est pas chargee, ne pas proposer d'ajouter une valeur peut-etre deja suivie.
    if (t.length >= 2 && valeurs) liste.push({ nom: `Chercher « ${texte.trim()} » sur Yahoo et l'ajouter`, lien: `/valeurs?ajouter=${encodeURIComponent(texte.trim())}`, type: 'Ajouter' })
    return liste
  }, [texte, valeurs])

  const aller = r => { entreeEnAttente.current = false; setOuverte(false); naviguer(r.lien) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (valeurs && entreeEnAttente.current && resultats[0]) aller(resultats[0]) }, [valeurs])
  if (!ouverte) return null
  return (
    <div className="modale-fond" style={{ alignItems: 'flex-start', paddingTop: '12vh' }} onMouseDown={e => e.target === e.currentTarget && setOuverte(false)}>
      <div className="modale palette">
        <input ref={champ} autoFocus className="champ palette-champ" placeholder="Valeur, symbole, ISIN ou page…" value={texte}
               onChange={e => { setTexte(e.target.value); setChoix(0) }}
               onKeyDown={e => {
                 if (e.key === 'Escape') setOuverte(false)
                 if (e.key === 'ArrowDown') { e.preventDefault(); setChoix(c => Math.min(c + 1, resultats.length - 1)) }
                 if (e.key === 'ArrowUp') { e.preventDefault(); setChoix(c => Math.max(c - 1, 0)) }
                 if (e.key === 'Enter' && valeurs === null) entreeEnAttente.current = true
                 else if (e.key === 'Enter' && resultats[choix]) aller(resultats[choix])
               }} />
        <div className="palette-resultats">
          {resultats.map((r, i) => (
            <button key={r.type + r.lien} className={`palette-ligne${i === choix ? ' actif' : ''}`} onMouseEnter={() => setChoix(i)} onClick={() => aller(r)}>
              <span>{r.nom} {r.detail && <span className="valeur-symbole">{r.detail}</span>}</span>
              <span className="etiquette">{r.type}</span>
            </button>
          ))}
        </div>
        <div className="palette-aide discret">↑ ↓ pour choisir · Entrée pour ouvrir · Échap pour fermer · Ctrl+K ou / pour rouvrir</div>
      </div>
    </div>
  )
}
