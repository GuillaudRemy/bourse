import { NavLink } from 'react-router-dom'

const LIENS = [
  { to: '/valeurs', label: 'Valeurs' },
  { to: '/methode', label: 'Méthode' },
]

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-marque">Bourse<span>.</span></div>
      <div className="nav-liens">
        {LIENS.map(lien => (
          <NavLink
            key={lien.to}
            to={lien.to}
            className={({ isActive }) => `nav-lien${isActive ? ' actif' : ''}`}
          >
            {lien.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
