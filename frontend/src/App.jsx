import { Routes, Route, Navigate } from 'react-router-dom'
import Nav from './components/Nav'
import Palette from './components/Palette'
import Bienvenue from './components/Bienvenue'
import Glossaire from './pages/Glossaire'
import Tableau from './pages/Tableau'
import Fiche   from './pages/Fiche'
import Methode from './pages/Methode'
import Reglages from './pages/Reglages'
import Accueil from './pages/Accueil'
import Portefeuille from './pages/Portefeuille'
import Calendrier from './pages/Calendrier'
import Alertes from './pages/Alertes'
import Screener from './pages/Screener'
import Comparer from './pages/Comparer'
import Backtest from './pages/Backtest'

export default function App() {
  return (
    <>
      <Nav />
      <Palette />
      <Bienvenue />
      <Routes>
        <Route path="/"            element={<Navigate to="/accueil" replace />} />
        <Route path="/accueil"     element={<Accueil />} />
        <Route path="/portefeuille" element={<Portefeuille />} />
        <Route path="/calendrier"  element={<Calendrier />} />
        <Route path="/alertes"     element={<Alertes />} />
        <Route path="/screener"    element={<Screener />} />
        <Route path="/comparer"    element={<Comparer />} />
        <Route path="/backtest"    element={<Backtest />} />
        <Route path="/glossaire"   element={<Glossaire />} />
        <Route path="/valeurs"     element={<Tableau />} />
        <Route path="/valeurs/:id" element={<Fiche />} />
        <Route path="/methode"     element={<Methode />} />
        <Route path="/reglages"    element={<Reglages />} />
        <Route path="*"            element={<Navigate to="/accueil" replace />} />
      </Routes>
    </>
  )
}
