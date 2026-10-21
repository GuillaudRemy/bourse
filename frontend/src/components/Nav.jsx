import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api } from '../lib/api'
import { lire, enregistrer, THEMES, TAILLES } from '../lib/apparence'

const LIENS = [
  { to: '/accueil',      label: 'Aujourd’hui' },
  { to: '/valeurs',      label: 'Valeurs' },
  { to: '/screener',     label: 'Screener' },
  { to: '/comparer',     label: 'Comparer' },
  { to: '/backtest',     label: 'Backtest' },
  { to: '/portefeuille', label: 'Portefeuille' },
  { to: '/calendrier',   label: 'Calendrier' },
  { to: '/methode',      label: 'Méthode' },
  { to: '/reglages',     label: 'Réglages' },
]

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

  return (
    <nav className="nav">
      <div className="nav-marque">Bourse<span>.</span></div>
      <div className="nav-liens">
        {LIENS.map(lien => (
          <NavLink key={lien.to} to={lien.to} className={({ isActive }) => `nav-lien${isActive ? ' actif' : ''}`}>
            {lien.label}
          </NavLink>
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
    </nav>
  )
}
