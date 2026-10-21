import { useCallback, useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, prix, date, dateHeure, ton } from '../lib/format'
import { TYPES } from '../lib/zones'
import OngletRegression   from '../components/fiche/OngletRegression'
import OngletTechnique    from '../components/fiche/OngletTechnique'
import OngletFondamentaux from '../components/fiche/OngletFondamentaux'
import OngletBenefices    from '../components/fiche/OngletBenefices'
import OngletQualite      from '../components/fiche/OngletQualite'
import OngletValorisation from '../components/fiche/OngletValorisation'
import OngletJournal      from '../components/fiche/OngletJournal'
import OngletDonnees      from '../components/fiche/OngletDonnees'

const ONGLETS = [
  { cle: 'regression',   libelle: 'Droite de régression' },
  { cle: 'technique',    libelle: 'Analyse technique' },
  { cle: 'benefices',    libelle: 'Bénéfices' },
  { cle: 'qualite',      libelle: 'Qualité' },
  { cle: 'valorisation', libelle: 'Valorisation' },
  { cle: 'journal',      libelle: 'Journal' },
  { cle: 'fondamentaux', libelle: 'Fondamentaux' },
  { cle: 'donnees',      libelle: 'Données & réglages' },
]

export default function Fiche() {
  const { id } = useParams()
  const [recherche, setRecherche] = useSearchParams()
  const onglet = recherche.get('onglet') || 'regression'

  const [analyse, setAnalyse] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [avertissement, setAvertissement] = useState(null)
  const [dividendes, setDividendes] = useState(true)
  const [debut, setDebut] = useState('')
  const [enEuros, setEnEuros] = useState(false)
  const [actualisation, setActualisation] = useState(false)

  const charger = useCallback(async () => {
    try {
      setAnalyse(await api.valeurs.analyse(id, { dividendes, debut, en_euros: enEuros || undefined }))
      setErreur(null)
    } catch (e) { setErreur(e.message) }
  }, [id, dividendes, debut, enEuros])

  useEffect(() => { charger() }, [charger])

  const actualiser = async () => {
    setActualisation(true)
    try {
      const r = await api.valeurs.actualiser(id)
      setAvertissement(r.avertissements?.length ? r.avertissements.join(' · ') : null)
      await charger()
    }
    catch (e) { setErreur(e.message) }
    finally { setActualisation(false) }
  }

  if (!analyse) {
    return (
      <div className="page">
        <Link to="/valeurs" className="retour">← Valeurs</Link>
        {erreur ? <div className="erreur">{erreur}</div> : <div className="chargement">Chargement…</div>}
      </div>
    )
  }

  const { valeur, stats } = analyse

  return (
    <div className="page">
      <Link to="/valeurs" className="retour">← Valeurs</Link>

      <div className="fiche-entete">
        <div>
          <h1 className="fiche-titre">{valeur.nom}</h1>
          <div className="fiche-meta">
            <span className="mono">{valeur.symbole}</span>
            <span className="etiquette">{TYPES[valeur.type]}</span>
            {valeur.secteur && <span className="etiquette">{valeur.secteur}</span>}
            {valeur.place && <span>{valeur.place}</span>}
            {valeur.pays && <span>· {valeur.pays}</span>}
            <span className="discret">
              · {valeur.source === 'yahoo' ? `Yahoo Finance, actualisé ${dateHeure(valeur.maj_le)}` : 'données importées'}
            </span>
            <button className="btn btn-mini" onClick={actualiser} disabled={actualisation}
                    title={valeur.source === 'yahoo' ? 'Cours, divisions et comptes' : 'Comptes officiels (ESEF, SEC)'}>
              {actualisation ? 'Actualisation…' : 'Actualiser'}
            </button>
            <a className="btn btn-mini" href={`/valeurs/${valeur.id}/rapport`} target="_blank" rel="noreferrer">Rapport PDF</a>
            <a className="btn btn-mini" href={`/api/valeurs/${valeur.id}/export.xlsx`}>Excel</a>
          </div>
        </div>
        {stats && (
          <div className="fiche-cours">
            <div className="fiche-dernier">{prix(stats.dernier, analyse.devise_affichee)}</div>
            <div className={`mono ${ton(stats.variation_jour)}`}>
              {pct(stats.variation_jour, { signe: true, decimales: 2 })}
              <span className="discret"> · {date(stats.jour)}</span>
            </div>
          </div>
        )}
      </div>

      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {analyse.qualite?.statut === 'alerte' && onglet !== 'donnees' && (
        <div className="info" style={{ marginBottom: 12, background: 'var(--erreur-bg)', color: 'var(--danger)', borderColor: 'var(--erreur-bord)' }}>
          <span>Données de cours suspectes : {analyse.qualite.anomalies.filter(a => a.gravite === 'alerte').length} anomalie(s) grave(s).</span>
          <button className="btn btn-mini" onClick={() => setRecherche({ onglet: 'donnees' })}>Voir</button>
        </div>
      )}
      {avertissement && (
        <div className="info" style={{ marginBottom: 12 }}>
          <span>{avertissement}</span>
          <button className="btn btn-mini btn-fantome" onClick={() => setAvertissement(null)}>×</button>
        </div>
      )}

      <div className="onglets">
        {ONGLETS.map(o => (
          <button
            key={o.cle} className={`onglet${onglet === o.cle ? ' actif' : ''}`}
            onClick={() => setRecherche(o.cle === 'regression' ? {} : { onglet: o.cle }, { replace: true })}
          >
            {o.libelle}
          </button>
        ))}
      </div>

      {analyse.vide && onglet !== 'donnees' ? (
        <div className="carte vide">
          Aucun cours pour cette valeur.{' '}
          <button className="btn btn-mini" onClick={() => setRecherche({ onglet: 'donnees' })}>Importer un fichier</button>
        </div>
      ) : (
        <>
          {onglet === 'regression' && (
            <OngletRegression
              analyse={analyse}
              dividendes={dividendes} setDividendes={setDividendes}
              enEuros={enEuros} setEnEuros={setEnEuros}
              debut={debut} setDebut={setDebut}
            />
          )}
          {onglet === 'technique'    && <OngletTechnique analyse={analyse} enEuros={enEuros} setEnEuros={setEnEuros} />}
          {onglet === 'benefices'    && <OngletBenefices analyse={analyse} />}
          {onglet === 'qualite'      && <OngletQualite analyse={analyse} />}
          {onglet === 'valorisation' && <OngletValorisation key={analyse.valeur.id} analyse={analyse} />}
          {onglet === 'journal'      && <OngletJournal analyse={analyse} />}
          {onglet === 'fondamentaux' && <OngletFondamentaux analyse={analyse} recharger={charger} />}
          {onglet === 'donnees'      && <OngletDonnees analyse={analyse} recharger={charger} />}
        </>
      )}
    </div>
  )
}
