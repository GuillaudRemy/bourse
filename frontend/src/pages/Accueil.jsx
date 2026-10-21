import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, prix, sigma, date, dateHeure, ton } from '../lib/format'
import { BadgeZone } from '../components/Jauge'
import { Stat } from '../components/fiche/OngletRegression'

const EVENEMENTS = { resultats: 'Résultats', detachement: 'Détachement du dividende', paiement: 'Paiement du dividende' }

export default function Accueil() {
  const [r, setR] = useState(null)
  const [erreur, setErreur] = useState(null)
  useEffect(() => { api.resume().then(setR).catch(e => setErreur(e.message)) }, [])

  if (erreur) return <div className="page"><div className="erreur">{erreur}</div></div>
  if (!r) return <div className="page"><div className="chargement">Chargement…</div></div>

  const p = r.portefeuille
  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Aujourd'hui</h1>
          <div className="page-sous-titre">
            {r.nombre_valeurs} valeur(s) suivie(s) · dernière actualisation complète : {r.derniere_actualisation ? date(r.derniere_actualisation) : 'jamais'}
          </div>
        </div>
      </div>

      <div className="stat-grille">
        <Stat libelle="Portefeuille" valeur={p ? prix(p.valeur, '€') : '—'}
              detail={p ? <>aujourd'hui <span className={ton(p.variation_jour)}>{pct(p.variation_jour, { signe: true, decimales: 2 })}</span></> : <Link to="/portefeuille">Saisir vos positions</Link>} />
        <Stat aide="pru" libelle="Plus-value latente" valeur={p ? prix(p.plus_value_latente, '€') : '—'} classe={p ? ton(p.plus_value_latente) : ''}
              detail={p ? `performance ${pct(p.twr, { signe: true })} depuis le début` : ''} />
        <Stat libelle="Alertes non lues" valeur={r.alertes.non_lus} classe={r.alertes.non_lus ? 'negatif' : ''}
              detail={<Link to="/alertes">Voir les alertes</Link>} />
        <Stat libelle="Dans les 14 jours" valeur={r.evenements.length} detail="résultats, dividendes" />
      </div>

      <div className="grille-2" style={{ marginTop: 16 }}>
        <div className="pile" style={{ gap: 16 }}>
          <Liste titre="Sous leur droite — à regarder" lignes={r.opportunites} vide="Aucune valeur sous sa droite d'au moins 1 écart-type."
                 detail={l => <><BadgeZone zone={l.zone} /> <span className="mono">{sigma(l.position)}</span></>} />
          <Liste titre="Tout en haut du couloir — prudence" lignes={r.cheres} vide="Aucune valeur au-dessus de +2 écarts-types."
                 detail={l => <><BadgeZone zone={l.zone} /> <span className="mono">{sigma(l.position)}</span></>} />
          <div className="grille-2" style={{ gridTemplateColumns: '1fr 1fr' }}>
            <Liste titre="Plus fortes hausses" lignes={r.hausses} vide="—"
                   detail={l => <span className="mono positif">{pct(l.variation_jour, { signe: true, decimales: 2 })}</span>} />
            <Liste titre="Plus fortes baisses" lignes={r.baisses} vide="—"
                   detail={l => <span className="mono negatif">{pct(l.variation_jour, { signe: true, decimales: 2 })}</span>} />
          </div>
        </div>
        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Dernières alertes</div>
            {r.alertes.liste.length === 0 && <div className="vide">Aucune alerte.</div>}
            {r.alertes.liste.map(a => (
              <div key={a.id} className="signal">
                <span className={`signal-point ${a.lu ? 'neutre' : 'baisse'}`} />
                <span style={{ flex: 1 }}>{a.message}</span>
                <span className="discret">{dateHeure(a.moment)}</span>
              </div>
            ))}
          </div>
          <div className="carte">
            <div className="section-titre">À venir</div>
            {r.evenements.length === 0 && <div className="vide">Rien dans les 14 prochains jours.</div>}
            {r.evenements.map((e, i) => (
              <div key={i} className="signal">
                <span className="mono" style={{ minWidth: 90 }}>{date(e.jour)}</span>
                <Link to={`/valeurs/${e.valeur_id}`} className="lien-poste" style={{ flex: 1 }}>{e.nom}</Link>
                <span className="discret">{EVENEMENTS[e.type] ?? e.type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function Liste({ titre, lignes, vide, detail }) {
  return (
    <div className="carte">
      <div className="section-titre">{titre}</div>
      {lignes.length === 0 && <div className="carte-corps discret">{vide}</div>}
      {lignes.map(l => (
        <div key={l.id} className="signal">
          <Link to={`/valeurs/${l.id}`} className="lien-poste" style={{ flex: 1 }}>{l.nom}</Link>
          <span className="mono">{prix(l.dernier, l.devise)}</span>
          {detail(l)}
        </div>
      ))}
    </div>
  )
}
