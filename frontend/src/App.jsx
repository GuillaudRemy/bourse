import { Routes, Route, Navigate } from 'react-router-dom'
import Nav from './components/Nav'
import Tableau from './pages/Tableau'
import Fiche   from './pages/Fiche'
import Methode from './pages/Methode'
import Reglages from './pages/Reglages'

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/"            element={<Navigate to="/valeurs" replace />} />
        <Route path="/valeurs"     element={<Tableau />} />
        <Route path="/valeurs/:id" element={<Fiche />} />
        <Route path="/methode"     element={<Methode />} />
        <Route path="/reglages"    element={<Reglages />} />
        <Route path="*"            element={<Navigate to="/valeurs" replace />} />
      </Routes>
    </>
  )
}
