import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { prix, pct, date, ton, unite } from '../lib/format'
import OngletRegression from '../components/fiche/OngletRegression'
import OngletBenefices from '../components/fiche/OngletBenefices'
import OngletQualite from '../components/fiche/OngletQualite'
import OngletValorisation from '../components/fiche/OngletValorisation'

/** Rapport imprimable d'une valeur : droite, benefices, qualite, valorisation, sur une seule page. */
export default function Rapport() {
  const { id } = useParams()
  const [analyse, setAnalyse] = useState(null)
  const [erreur, setErreur] = useState(null)
  useEffect(() => { api.valeurs.analyse(id, {}).then(setAnalyse).catch(e => setErreur(e.message)) }, [id])
  if (erreur) return <div className="page"><div className="erreur">{erreur}</div></div>
  if (!analyse) return <div className="page"><div className="chargement">Préparation du rapport…</div></div>
  const { valeur, stats } = analyse
  const rien = () => {}
  return (
    <div className="page rapport">
      <div className="rangee no-print" style={{ marginBottom: 16 }}>
        <button className="btn btn-primaire" onClick={() => window.print()}>Imprimer ou enregistrer en PDF</button>
        <span className="discret">Dans la fenêtre d'impression, choisissez « Enregistrer au format PDF ».</span>
      </div>
      <div className="fiche-entete">
        <div>
          <h1 className="fiche-titre">{valeur.nom}</h1>
          <div className="fiche-meta"><span className="mono">{valeur.symbole}</span>{valeur.secteur && <span>· {valeur.secteur}</span>}
            <span className="discret">· rapport du {date(new Date().toISOString())}</span></div>
        </div>
        <div className="fiche-cours">
          <div className="fiche-dernier">{prix(stats?.dernier, unite(valeur))}</div>
          <div className={`mono ${ton(stats?.variation_jour)}`}>{pct(stats?.variation_jour, { signe: true, decimales: 2 })} · {date(stats?.jour)}</div>
        </div>
      </div>
      {[['Droite de régression', <OngletRegression key="r" analyse={analyse} dividendes setDividendes={rien} debut="" setDebut={rien} enEuros={false} setEnEuros={rien} />],
        ['Bénéfices', <OngletBenefices key="b" analyse={analyse} />],
        ['Qualité', <OngletQualite key="q" analyse={analyse} />],
        ['Valorisation', <OngletValorisation key="v" analyse={analyse} />]].map(([titre, contenu]) => (
        <section key={titre} className="rapport-section">
          <h2 className="rapport-titre">{titre}</h2>
          {contenu}
        </section>
      ))}
      <p className="discret" style={{ marginTop: 24 }}>Bourse — outil d'aide à l'analyse, pas un conseil en investissement. La droite donne le cadre, les comptes la valident.</p>
    </div>
  )
}
