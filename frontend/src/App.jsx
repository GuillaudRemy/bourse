import { Routes, Route, Navigate } from 'react-router-dom'
import Nav from './components/Nav'
import Tableau from './pages/Tableau'
import Fiche   from './pages/Fiche'
import Methode from './pages/Methode'
import Reglages from './pages/Reglages'
import Accueil from './pages/Accueil'
import Portefeuille from './pages/Portefeuille'
import Calendrier from './pages/Calendrier'
import Alertes from './pages/Alertes'

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/"            element={<Navigate to="/accueil" replace />} />
        <Route path="/accueil"     element={<Accueil />} />
        <Route path="/portefeuille" element={<Portefeuille />} />
        <Route path="/calendrier"  element={<Calendrier />} />
        <Route path="/alertes"     element={<Alertes />} />
        <Route path="/valeurs"     element={<Tableau />} />
        <Route path="/valeurs/:id" element={<Fiche />} />
        <Route path="/methode"     element={<Methode />} />
        <Route path="/reglages"    element={<Reglages />} />
        <Route path="*"            element={<Navigate to="/accueil" replace />} />
      </Routes>
    </>
  )
}
