// @ts-check
import { useEffect, useState } from 'react'
import Modale from './Modale'

const CLE = 'bourse.bienvenue-vue'
const ETAPES = [
  ['Bienvenue', <>
    <p>Cette application aide à choisir des actions pour le <b>long terme</b>, avec une méthode simple : regarder où se situe le cours par rapport à sa <b>tendance de fond</b>, puis vérifier dans les comptes que cette tendance est solide.</p>
    <p>Cinq écrans pour en faire le tour.</p></>],
  ['La droite de régression', <>
    <p>Sur 20 ans, le cours d'une belle entreprise oscille autour d'une droite (en échelle logarithmique). Sa <b>pente</b> est le rythme de croisière de l'action ; l'<b>écart-type</b> est la largeur du couloir.</p>
    <p>Tout en bas du couloir (−2 σ), c'est rare et souvent une occasion ; tout en haut (+2 σ), prudence. Onglet « Droite de régression » de chaque valeur.</p></>],
  ['La droite donne le cadre, les comptes la valident', <>
    <p>Avant de se fier à une droite : au moins 20 ans d'historique, une pente portée par les <b>bénéfices</b> (et non par un PER qui gonfle), et une entreprise restée fidèle à elle-même.</p>
    <p>Les onglets « Bénéfices », « Qualité » et « Valorisation » font ces vérifications avec les comptes officiels.</p></>],
  ['Au quotidien', <>
    <p><b>Aujourd'hui</b> résume ce qui a bougé ; les <b>alertes</b> préviennent quand une valeur passe en bas ou en haut de son couloir ; le <b>portefeuille</b> suit vos positions, leur performance et leur fiscalité.</p>
    <p>Les données s'actualisent seules chaque jour au lancement.</p></>],
  ['Pour aller plus loin', <>
    <p><b>Ctrl + K</b> (ou la touche /) ouvre la recherche : une valeur, une page, ou une action à ajouter.</p>
    <p>Les « ? » à côté des chiffres en donnent la définition ; tout est aussi dans le <b>Glossaire</b>. Le thème sombre et la taille du texte se règlent en haut à droite.</p>
    <p className="discret">Outil d'aide à l'analyse, pas un conseil en investissement.</p></>],
]

export default function Bienvenue() {
  const [etape, setEtape] = useState(null)
  useEffect(() => {
    let vue = true
    try { vue = localStorage.getItem(CLE) === 'oui' } catch { /* stockage indisponible */ }
    if (!vue) setEtape(0)
    const revoir = () => setEtape(0)
    window.addEventListener('revoir-bienvenue', revoir)
    return () => window.removeEventListener('revoir-bienvenue', revoir)
  }, [])
  if (etape === null) return null
  const fermer = () => { try { localStorage.setItem(CLE, 'oui') } catch { /* stockage indisponible */ } setEtape(null) }
  const [titre, contenu] = ETAPES[etape]
  return (
    <Modale titre={titre} onFermer={fermer} pied={<>
      <button className="btn" onClick={fermer}>Passer</button>
      <div className="bienvenue-points">{ETAPES.map((_, i) => <span key={i} className={i === etape ? 'actif' : ''} />)}</div>
      <div className="rangee">
        {etape > 0 && <button className="btn" onClick={() => setEtape(etape - 1)}>Précédent</button>}
        {etape < ETAPES.length - 1
          ? <button className="btn btn-primaire" onClick={() => setEtape(etape + 1)}>Suivant</button>
          : <button className="btn btn-primaire" onClick={fermer}>Commencer</button>}
      </div>
    </>}>
      <div className="bienvenue-etape">{contenu}</div>
    </Modale>
  )
}
