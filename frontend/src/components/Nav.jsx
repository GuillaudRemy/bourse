// @ts-check
import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { lire, enregistrer, THEMES, TAILLES } from '../lib/apparence'

// Cinq entrees ; Outils et Aide s'ouvrent en liste deroulante. Les adresses ne changent pas (favoris intacts).
const MENU = [
  { label: 'Aujourd’hui',  to: '/accueil' },
  { label: 'Marchés',      to: '/valeurs' },
  { label: 'Portefeuille', to: '/portefeuille' },
  { label: 'Outils', pages: [['/screener', 'Screener'], ['/comparer', 'Comparer'], ['/calendrier', 'Calendrier'], ['/alertes', 'Alertes'],
                             ['/simulateur', 'Simulateur de patrimoine'], ['/backtest', 'Backtest'], ['/donnees', 'Couverture des données']] },
  { label: 'Aide',   pages: [['/methode', 'Méthode'], ['/glossaire', 'Glossaire'], ['/a-propos', 'À propos']] },
]
const dans = (chemin, page) => chemin === page || chemin.startsWith(page + '/')

export default function Nav() {
  const [nonLues, setNonLues] = useState(0)
  const [apparence, setApparence] = useState(lire)
  const suivant = (objet, actuel) => { const cles = Object.keys(objet); return cles[(cles.indexOf(actuel) + 1) % cles.length] }
  const changer = nouvelles => { setApparence(nouvelles); enregistrer(nouvelles) }

  // Cloche des alertes : verifiee chaque minute (les alertes arrivent avec les actualisations).
  useEffect(() => {
    let actif = true
    const verifier = () => api.alertes.declenchements().then(d => actif && setNonLues(d.non_lus)).catch(() => {})
    verifier()
    const minuterie = setInterval(verifier, 60000)
    window.addEventListener('alertes-lues', verifier)
    return () => { actif = false; clearInterval(minuterie); window.removeEventListener('alertes-lues', verifier) }
  }, [])

  const { pathname } = useLocation()
  const [ouvert, setOuvert] = useState(null)            // libelle de la liste deroulante ouverte
  const barre = useRef(null)
  useEffect(() => setOuvert(null), [pathname])
  useEffect(() => {
    if (!ouvert) return
    const clic = e => { if (!barre.current?.contains(e.target)) setOuvert(null) }
    const touche = e => { if (e.key === 'Escape') setOuvert(null) }
    document.addEventListener('mousedown', clic)
    document.addEventListener('keydown', touche)
    return () => { document.removeEventListener('mousedown', clic); document.removeEventListener('keydown', touche) }
  }, [ouvert])

  return (
    <nav className="nav">
      <div className="nav-marque">Bourse<span>.</span></div>
      <div className="nav-liens" ref={barre}>
        {MENU.map(e => e.to ? (
          <NavLink key={e.label} to={e.to} className={({ isActive }) => `nav-lien${isActive ? ' actif' : ''}`}>{e.label}</NavLink>
        ) : (
          <div key={e.label} className="nav-groupe">
            <button className={`nav-lien${e.pages.some(([page]) => dans(pathname, page)) ? ' actif' : ''}`} aria-haspopup="menu" aria-expanded={ouvert === e.label}
                    onClick={() => setOuvert(ouvert === e.label ? null : e.label)}>
              {e.label} <span aria-hidden="true" className="nav-fleche">▾</span>
            </button>
            {ouvert === e.label && (
              <div className="menu-deroulant" role="menu">
                {e.pages.map(([page, label]) => (
                  <NavLink key={page} to={page} role="menuitem" onClick={() => setOuvert(null)}
                           className={({ isActive }) => `menu-entree${isActive ? ' actif' : ''}`}>{label}</NavLink>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <span className="espaceur" />
      <button className="nav-lien recherche-nav" title="Rechercher (Ctrl+K)" onClick={() => window.dispatchEvent(new Event('ouvrir-palette'))}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
        <kbd>Ctrl K</kbd>
      </button>
      <button className="nav-lien" title={`Thème : ${THEMES[apparence.theme]} (cliquer pour changer)`}
              onClick={() => changer({ ...apparence, theme: suivant(THEMES, apparence.theme) })}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          {apparence.theme === 'sombre' && <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />}
          {apparence.theme === 'clair' && <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>}
          {apparence.theme === 'auto' && <><circle cx="12" cy="12" r="8" /><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" /></>}
        </svg>
      </button>
      <button className="nav-lien" title={`Taille du texte : ${TAILLES[apparence.taille][0]} (cliquer pour changer)`}
              onClick={() => changer({ ...apparence, taille: suivant(TAILLES, apparence.taille) })}>
        A<span style={{ fontSize: '0.75em' }}>A</span>
      </button>
      <NavLink to="/alertes" className={({ isActive }) => `nav-lien cloche${isActive ? ' actif' : ''}`} title="Alertes">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {nonLues > 0 && <span className="cloche-nombre">{nonLues}</span>}
      </NavLink>
      <NavLink to="/reglages" className={({ isActive }) => `nav-lien${isActive ? ' actif' : ''}`} title="Réglages" aria-label="Réglages">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </NavLink>
    </nav>
  )
}
