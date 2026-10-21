import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { pct, prix, nombre, sigma, date, ton } from '../lib/format'
import Modale from '../components/Modale'
import DepotFichier from '../components/DepotFichier'
import { BadgeZone } from '../components/Jauge'
import { Stat } from '../components/fiche/OngletRegression'
import GraphiquePerformance from '../components/GraphiquePerformance'

const TYPES_COMPTE = { PEA: 'PEA', 'PEA-PME': 'PEA-PME', CTO: 'Compte-titres', AV: 'Assurance-vie', autre: 'Autre' }
const TYPES_OP = { achat: 'Achat', vente: 'Vente', dividende: 'Dividende', frais: 'Frais', depot: 'Dépôt', retrait: 'Retrait', division: 'Division' }
const euros = v => prix(v, '€')

export default function Portefeuille() {
  const [compteId, setCompteId] = useState('')
  const [s, setS] = useState(null)
  const [operations, setOperations] = useState([])
  const [valeurs, setValeurs] = useState([])
  const [modale, setModale] = useState(null)       // 'compte' | 'operation' | 'releve'
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)

  const charger = useCallback(async () => {
    try {
      const [synthese, ops, vals] = await Promise.all([
        api.portefeuille.synthese(compteId || undefined), api.portefeuille.transactions(compteId || undefined), api.valeurs.list()])
      setS(synthese); setOperations(ops); setValeurs(vals); setErreur(null)
    } catch (e) { setErreur(e.message) }
  }, [compteId])
  useEffect(() => { charger() }, [charger])

  const fermer = message => { setModale(null); if (message) setInfo(message); charger() }
  if (!s) return <div className="page">{erreur ? <div className="erreur">{erreur}</div> : <div className="chargement">Chargement…</div>}</div>

  const comptes = s.comptes
  const nomValeur = Object.fromEntries(valeurs.map(v => [v.id, v.nom]))
  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">Portefeuille</h1>
          <div className="page-sous-titre">Positions, performance réelle, risque et fiscalité — montants en euros</div>
        </div>
        <div className="rangee" style={{ flexWrap: 'wrap' }}>
          <select className="champ" style={{ width: 'auto' }} value={compteId} onChange={e => setCompteId(e.target.value)}>
            <option value="">Tous les comptes</option>
            {comptes.map(c => <option key={c.id} value={c.id}>{c.nom} ({TYPES_COMPTE[c.type]})</option>)}
          </select>
          <button className="btn" onClick={() => setModale('compte')}>+ Compte</button>
          {compteId && <button className="btn" onClick={() => setModale('modifier')}>Modifier le compte</button>}
          <button className="btn" onClick={() => setModale('releve')} disabled={!comptes.length}>Importer un relevé</button>
          <button className="btn btn-primaire" onClick={() => setModale('operation')} disabled={!comptes.length}>+ Opération</button>
        </div>
      </div>
      {erreur && <div className="erreur" style={{ marginBottom: 12 }}>{erreur}</div>}
      {info && <div className="succes" style={{ marginBottom: 12 }}>{info}</div>}

      {!comptes.length ? (
        <div className="carte vide">
          Commencez par créer un compte (PEA, compte-titres…), puis saisissez vos opérations ou importez le relevé de votre courtier.
          <br /><button className="btn btn-primaire" style={{ marginTop: 12 }} onClick={() => setModale('compte')}>Créer un compte</button>
        </div>
      ) : s.vide ? (
        <div className="carte vide">Aucune opération pour l'instant.</div>
      ) : <Contenu s={s} />}

      {operations.length > 0 && (
        <div className="carte" style={{ marginTop: 16 }}>
          <div className="section-titre">Opérations</div>
          <div className="tableau-conteneur">
            <table className="tableau">
              <thead><tr><th>Date</th><th style={{ textAlign: 'left' }}>Type</th><th style={{ textAlign: 'left' }}>Valeur</th><th>Quantité</th><th>Prix</th><th>Frais</th><th>Montant (€)</th><th /></tr></thead>
              <tbody>
                {operations.map(o => (
                  <tr key={o.id}>
                    <td style={{ textAlign: 'left' }}>{date(o.jour)}</td>
                    <td className="texte">{TYPES_OP[o.type]}</td>
                    <td className="texte">{o.valeur_id ? <Link className="lien-poste" to={`/valeurs/${o.valeur_id}`}>{nomValeur[o.valeur_id]}</Link> : '—'}</td>
                    <td>{o.quantite ? nombre(o.quantite, 4).replace(/,?0+$/, '') : '—'}</td>
                    <td>{o.prix ? nombre(o.prix, 2) : '—'}</td>
                    <td title={o.ttf ? `dont TTF ${nombre(o.ttf, 2)} €` : ''}>{o.frais ? nombre(o.frais, 2) : '—'}{o.ttf ? <sup className="discret"> TTF</sup> : null}</td>
                    <td className={ton(o.montant)}>{nombre(o.montant, 2)}</td>
                    <td><button className="btn btn-mini btn-fantome" onClick={async () => { if (confirm('Supprimer cette opération ?')) { await api.portefeuille.supprimerTransaction(o.id); charger() } }}>×</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {modale === 'compte' && <ModaleCompte onFermer={fermer} />}
      {modale === 'modifier' && <ModaleCompte onFermer={fermer} compte={comptes.find(c => String(c.id) === String(compteId))} />}
      {modale === 'operation' && <ModaleOperation comptes={comptes} valeurs={valeurs} compteId={compteId} onFermer={fermer} />}
      {modale === 'releve' && <ModaleReleve comptes={comptes} compteId={compteId} onFermer={fermer} />}
    </div>
  )
}

function Contenu({ s }) {
  const t = s.totaux, p = s.performance, ref = p.reference
  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat libelle="Valeur totale" valeur={euros(t.valeur)} detail={<>aujourd'hui <span className={ton(t.variation_jour)}>{pct(t.variation_jour, { signe: true, decimales: 2 })}</span></>} />
        <Stat aide="pru" libelle="Plus-value latente" valeur={euros(t.plus_value_latente)} classe={ton(t.plus_value_latente)} detail={`coût ${euros(t.cout)}`} />
        <Stat libelle="Réalisé + dividendes" valeur={euros(t.plus_value_realisee + t.dividendes)} classe={ton(t.plus_value_realisee + t.dividendes)}
              detail={`dont dividendes ${euros(t.dividendes)} · frais ${euros(t.frais)}`} />
        <Stat aide="tri" libelle="Rendement réel (TRI)" valeur={pct(p.xirr, { signe: true })} detail="par an, apports et retraits compris" />
        <Stat aide="twr" libelle="Performance (TWR)" valeur={pct(p.twr, { signe: true })}
              detail={p.twr_annualise != null ? `soit ${pct(p.twr_annualise, { signe: true })}/an` : 'moins d’un an'} />
        <Stat libelle={`Référence : ${ref?.nom ?? '—'}`} valeur={ref?.twr != null ? pct(ref.twr, { signe: true }) : '—'}
              detail={ref?.manquante ? `ajoutez ${ref.manquante} à vos valeurs` : ref ? `même argent, mêmes dates · TRI ${pct(ref.xirr, { signe: true })}` : ''} />
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Performance cumulée — portefeuille (couleur) et référence (gris)</div>
          <GraphiquePerformance serie={p.serie} />
          <div className="carte-corps discret">
            La performance pondérée par le temps (TWR) neutralise vos apports et retraits : elle mesure vos choix de titres.
            Le rendement réel (TRI) tient compte du moment où vous avez apporté l'argent : c'est ce que vous avez vraiment gagné.
          </div>
        </div>
        <div className="carte">
          <div className="section-titre">Risque</div>
          <dl className="liste-cle">
            <div><dt>Volatilité annuelle</dt><dd>{pct(p.risque?.volatilite)}</dd></div>
            <div><dt>Perte maximale</dt><dd>{pct(p.risque?.perte_max)}</dd></div>
            <div><dt>Bêta (vs référence)</dt><dd>{nombre(p.risque?.beta, 2)}</dd></div>
            <div><dt>Corrélation (vs référence)</dt><dd>{nombre(p.risque?.correlation, 2)}</dd></div>
            <div><dt>Nombre de lignes</dt><dd>{s.concentration.lignes}</dd></div>
            <div><dt>Poids de la 1ʳᵉ ligne</dt><dd>{pct(s.concentration.premiere)}</dd></div>
            <div><dt>Poids des 5 premières</dt><dd>{pct(s.concentration.cinq_premieres)}</dd></div>
          </dl>
        </div>
      </div>

      <div className="carte">
        <div className="section-titre">Positions</div>
        <div className="tableau-conteneur">
          <table className="tableau">
            <thead><tr><th>Valeur</th><th>Quantité</th><th>PRU (€)</th><th>Cours (€)</th><th>Valeur (€)</th><th>Poids</th><th>+/- latente</th><th>Jour</th><th>Position</th><th>Zone</th><th>PEA</th></tr></thead>
            <tbody>
              {s.positions.filter(l => l.quantite > 1e-9).map(l => (
                <tr key={l.valeur_id}>
                  <td className="texte"><Link className="lien-poste" to={`/valeurs/${l.valeur_id}`}>{l.nom}</Link><div className="valeur-symbole">{l.symbole}</div></td>
                  <td>{nombre(l.quantite, 4).replace(/,?0+$/, '')}</td>
                  <td>{nombre(l.pru, 2)}</td>
                  <td>{nombre(l.cours_eur, 2)}</td>
                  <td>{nombre(l.valeur_actuelle, 0)}</td>
                  <td>{pct(l.poids)}</td>
                  <td className={ton(l.plus_value_latente)}>{nombre(l.plus_value_latente, 0)} <span className="discret">({pct(l.plus_value_latente_pct, { signe: true })})</span></td>
                  <td className={ton(l.variation_jour)}>{pct(l.variation_jour, { signe: true, decimales: 2 })}</td>
                  <td>{sigma(l.position)}</td>
                  <td><BadgeZone zone={l.zone} /></td>
                  <td>{l.eligible_pea === true ? '✓' : l.eligible_pea === false ? '✕' : '?'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="resume-grille">
        {[['secteur', 'Par secteur'], ['pays', 'Par pays'], ['devise', 'Par devise']].map(([cle, titre]) => (
          <div key={cle} className="carte">
            <div className="section-titre">{titre}</div>
            {s.repartitions[cle].map(g => (
              <div key={g.nom} className="ligne-totale">
                <span className="ligne-nom">{g.nom}</span>
                <span className="ligne-duree">{euros(g.valeur)}</span>
                <span className="ligne-part">{pct(g.poids, { decimales: 0 })}</span>
                <div className="barre"><div className="barre-remplie" style={{ width: `${g.poids * 100}%`, background: 'var(--accent)' }} /></div>
              </div>
            ))}
          </div>
        ))}
      </div>

      {s.correlations.ids?.length > 1 && <Correlations c={s.correlations} />}
      <Fiscalite f={s.fiscalite} />
    </div>
  )
}

function Correlations({ c }) {
  const couleur = v => v === null ? 'transparent' : v > 0 ? `rgba(220, 38, 38, ${Math.min(1, v) * 0.55})` : `rgba(5, 150, 105, ${Math.min(1, -v) * 0.55})`
  return (
    <div className="carte">
      <div className="section-titre">Corrélations (rendements hebdomadaires, 3 ans) — rouge : bougent ensemble, vert : se compensent</div>
      <div className="tableau-conteneur">
        <table className="tableau">
          <thead><tr><th />{c.ids.map(id => <th key={id} style={{ textAlign: 'center' }}>{c.noms[id]?.slice(0, 12)}</th>)}</tr></thead>
          <tbody>
            {c.ids.map((id, i) => (
              <tr key={id}>
                <td className="texte">{c.noms[id]}</td>
                {c.valeurs[i].map((v, j) => <td key={j} style={{ textAlign: 'center', background: i === j ? 'var(--surface-2)' : couleur(v) }}>{i === j ? '' : nombre(v, 2)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Fiscalite({ f }) {
  const taux = v => pct(v, { decimales: 1 })
  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="resume-grille">
        {f.comptes.map(c => (
          <div key={c.compte_id} className="carte">
            <div className="section-titre">Fiscalité — {c.nom} ({TYPES_COMPTE[c.type]})</div>
            {c.plafond !== undefined && (
              <>
                <dl className="liste-cle">
                  <div><dt>Versements</dt><dd>{euros(c.versements)} / {euros(c.plafond)}</dd></div>
                  <div><dt>Reste à verser</dt><dd className={c.reste < 0 ? 'negatif' : ''}>{euros(c.reste)}</dd></div>
                  <div><dt>Ouvert le · ancienneté</dt><dd>{date(c.ouverture)} · {nombre(c.anciennete, 1)} ans</dd></div>
                  <div><dt>Gain latent (valeur {euros(c.valeur)})</dt><dd>{euros(c.gain_latent)}</dd></div>
                  <div><dt>Si retrait total aujourd'hui</dt><dd>{euros(c.impot_retrait)} <span className="discret">({taux(c.taux_retrait)} du gain)</span></dd></div>
                  {c.non_eligibles.length > 0 && <div><dt className="negatif">Titres non éligibles</dt><dd className="negatif">{c.non_eligibles.join(', ')}</dd></div>}
                </dl>
                <div className="carte-corps discret">
                  {c.cinq_ans
                    ? <>Plus de 5 ans : les gains sont exonérés d'impôt sur le revenu, mais les prélèvements sociaux ({taux(f.prelevements_sociaux)}) restent dus au retrait.
                        Un retrait partiel ne clôture pas le plan et les versements restent possibles. Certaines analyses appliquent
                        l'ancien taux de 17,2 % à la part des gains acquis avant 2026 : à vérifier avec votre banque.</>
                    : <>Moins de 5 ans : un retrait, même partiel, clôture en principe le plan (sauf licenciement, invalidité, retraite anticipée,
                        titres d'une société liquidée, ou création d'entreprise) et les gains sont imposés à la flat tax de {taux(f.pfu)}.</>}
                </div>
              </>
            )}
            {c.annees !== undefined && (
              <>
                {c.annees.length === 0 && <div className="carte-corps discret">Aucune vente ni dividende pour l'instant.</div>}
                {c.annees.length > 0 && (
                  <div className="tableau-conteneur">
                    <table className="tableau">
                      <thead><tr><th>Année</th><th>Plus-values</th><th>Moins-values</th><th>Reports imputés</th><th>Dividendes</th><th>Flat tax</th>{f.tmi !== null && <th>Barème ({taux(f.tmi)})</th>}<th>Report restant</th></tr></thead>
                      <tbody>
                        {c.annees.map(a => (
                          <tr key={a.annee}>
                            <td style={{ textAlign: 'left' }}>{a.annee}</td>
                            <td>{nombre(a.plus_values, 0)}</td><td>{nombre(a.moins_values, 0)}</td>
                            <td>{nombre(a.moins_values_anterieures_imputees, 0)}</td><td>{nombre(a.dividendes, 0)}</td>
                            <td title={`taux ${taux(a.taux_pfu)}`}>{euros(a.impot_pfu)}</td>
                            {f.tmi !== null && <td className={a.impot_bareme < a.impot_pfu ? 'positif' : ''}>{euros(a.impot_bareme)}</td>}
                            <td>{euros(a.report_disponible)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="carte-corps discret">
                  Flat tax (PFU) de {taux(f.pfu)} depuis 2026 : {taux(f.impot_revenu)} d'impôt sur le revenu + {taux(f.prelevements_sociaux)} de
                  prélèvements sociaux (30 % jusqu'en 2025, quand les prélèvements étaient de 17,2 %). Les moins-values s'imputent sur les
                  plus-values de l'année puis des 10 années suivantes. L'option pour le barème progressif (abattement de 40 % sur les dividendes,
                  prélèvements sociaux toujours dus) s'applique à tous les revenus de placement de l'année ;
                  {f.tmi === null ? ' indiquez votre tranche marginale dans les Réglages pour la comparer.' : ' en vert, elle serait plus avantageuse.'}
                </div>
              </>
            )}
            {c.plafond === undefined && c.annees === undefined && <div className="carte-corps discret">Enveloppe sans suivi fiscal ici (assurance-vie : fiscalité selon l'ancienneté du contrat).</div>}
          </div>
        ))}
      </div>
      {f.plafond_commun.verse > 0 && (
        <div className="discret">PEA et PEA-PME : {euros(f.plafond_commun.verse)} versés sur le plafond commun de {euros(f.plafond_commun.plafond)} (150 000 € au plus sur le PEA classique).</div>
      )}
      <div className="discret">
        Estimations indicatives, sources : <a className="lien-poste" href="https://www.service-public.gouv.fr/particuliers/vosdroits/F21618" target="_blank" rel="noreferrer">service-public.gouv.fr (plus-values)</a>,{' '}
        <a className="lien-poste" href="https://www.service-public.gouv.fr/particuliers/vosdroits/F2385" target="_blank" rel="noreferrer">service-public.gouv.fr (PEA)</a>. L'IFU de votre établissement et votre déclaration font foi.
      </div>
    </div>
  )
}

function ModaleCompte({ onFermer, compte }) {
  const vide = v => v === null || v === undefined ? '' : String(v).replace('.', ',')
  const [c, setC] = useState(compte ? {
    nom: compte.nom, type: compte.type, ouverture: compte.ouverture ?? '', courtier: compte.courtier ?? '',
    frais_fixe: vide(compte.frais_fixe), frais_pct: compte.frais_pct == null ? '' : vide(+(compte.frais_pct * 100).toFixed(4)),
    frais_min: vide(compte.frais_min),
  } : { nom: '', type: 'PEA', ouverture: '', courtier: '', frais_fixe: '', frais_pct: '', frais_min: '' })
  const [erreur, setErreur] = useState(null)
  const n = v => v === '' ? null : Number(String(v).replace(',', '.'))
  const enregistrer = async () => {
    try {
      const donnees = { nom: c.nom, type: c.type, ouverture: c.ouverture || null, courtier: c.courtier || null,
        frais_fixe: n(c.frais_fixe), frais_pct: c.frais_pct === '' ? null : n(c.frais_pct) / 100, frais_min: n(c.frais_min) }
      if (compte) await api.portefeuille.modifierCompte(compte.id, donnees)
      else await api.portefeuille.creerCompte(donnees)
      onFermer(compte ? 'Compte modifié.' : 'Compte créé.')
    } catch (e) { setErreur(e.message) }
  }
  return (
    <Modale titre={compte ? `Modifier « ${compte.nom} »` : 'Nouveau compte'} onFermer={() => onFermer()} pied={<><button className="btn" onClick={() => onFermer()}>Annuler</button><button className="btn btn-primaire" onClick={enregistrer} disabled={!c.nom.trim()}>{compte ? 'Enregistrer' : 'Créer'}</button></>}>
      <div className="champ-groupe"><label className="champ-label">Nom</label><input className="champ" autoFocus value={c.nom} onChange={e => setC({ ...c, nom: e.target.value })} placeholder="PEA Boursorama" /></div>
      <div className="champ-groupe"><label className="champ-label">Type</label>
        <select className="champ" value={c.type} onChange={e => setC({ ...c, type: e.target.value })}>{Object.entries(TYPES_COMPTE).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
      <div className="champ-groupe"><label className="champ-label">Date d'ouverture (compte le délai de 5 ans du PEA)</label><input type="date" className="champ" value={c.ouverture} onChange={e => setC({ ...c, ouverture: e.target.value })} /></div>
      <div className="champ-groupe"><label className="champ-label">Courtier</label><input className="champ" value={c.courtier} onChange={e => setC({ ...c, courtier: e.target.value })} /></div>
      <div className="champ-groupe">
        <label className="champ-label">Frais de courtage par ordre (vide : réglages par défaut)</label>
        <div className="rangee">
          <input className="champ champ-mono" placeholder="Fixe (€)" value={c.frais_fixe} onChange={e => setC({ ...c, frais_fixe: e.target.value })} />
          <span>+</span>
          <input className="champ champ-mono" placeholder="Proportion (%)" value={c.frais_pct} onChange={e => setC({ ...c, frais_pct: e.target.value })} />
          <input className="champ champ-mono" placeholder="Minimum (€)" value={c.frais_min} onChange={e => setC({ ...c, frais_min: e.target.value })} />
        </div>
        <span className="discret">Exemple : 1 € + 0,1 %, minimum 0 €. La TTF (0,4 % sur les achats d'actions françaises de plus d'un milliard) s'ajoute automatiquement.</span>
      </div>
      {erreur && <div className="erreur">{erreur}</div>}
    </Modale>
  )
}

function ModaleOperation({ comptes, valeurs, compteId, onFermer }) {
  const [o, setO] = useState({ compte_id: compteId || comptes[0]?.id, jour: new Date().toISOString().slice(0, 10), type: 'achat', valeur_id: '', quantite: '', prix: '', frais: '', montant: '' })
  const [erreur, setErreur] = useState(null)
  const n = v => v === '' || v === null ? null : Number(String(v).replace(',', '.'))
  const titres = ['achat', 'vente', 'dividende', 'division'].includes(o.type)
  const [apercu, setApercu] = useState(null)
  useEffect(() => {
    if (!['achat', 'vente'].includes(o.type) || !n(o.quantite) || !n(o.prix) || o.frais !== '') { setApercu(null); return }
    const minuterie = setTimeout(() => api.portefeuille.frais({ compte_id: o.compte_id, type: o.type, quantite: n(o.quantite),
      prix: n(o.prix), jour: o.jour, valeur_id: o.valeur_id || undefined }).then(setApercu).catch(() => setApercu(null)), 300)
    return () => clearTimeout(minuterie)
  }, [o.type, o.quantite, o.prix, o.frais, o.jour, o.valeur_id, o.compte_id])
  const enregistrer = async () => {
    try {
      await api.portefeuille.creerTransaction({ compte_id: Number(o.compte_id), jour: o.jour, type: o.type, valeur_id: o.valeur_id ? Number(o.valeur_id) : null,
        quantite: n(o.quantite), prix: n(o.prix), frais: n(o.frais) ?? 0, montant: n(o.montant) })
      onFermer('Opération enregistrée.')
    } catch (e) { setErreur(e.message) }
  }
  return (
    <Modale titre="Nouvelle opération" onFermer={() => onFermer()} pied={<><button className="btn" onClick={() => onFermer()}>Annuler</button><button className="btn btn-primaire" onClick={enregistrer}>Enregistrer</button></>}>
      <div className="rangee">
        <select className="champ" value={o.compte_id} onChange={e => setO({ ...o, compte_id: e.target.value })}>{comptes.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}</select>
        <input type="date" className="champ" style={{ width: 160 }} value={o.jour} onChange={e => setO({ ...o, jour: e.target.value })} />
      </div>
      <select className="champ" value={o.type} onChange={e => setO({ ...o, type: e.target.value })}>{Object.entries(TYPES_OP).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      {titres && (
        <select className="champ" value={o.valeur_id} onChange={e => setO({ ...o, valeur_id: e.target.value })}>
          <option value="">— valeur (à ajouter d'abord dans « Valeurs » si absente) —</option>
          {valeurs.map(v => <option key={v.id} value={v.id}>{v.nom} ({v.symbole})</option>)}
        </select>
      )}
      {['achat', 'vente'].includes(o.type) && (
        <div className="rangee">
          <input className="champ champ-mono" placeholder="Quantité" value={o.quantite} onChange={e => setO({ ...o, quantite: e.target.value })} />
          <input className="champ champ-mono" placeholder="Prix unitaire (devise du titre)" value={o.prix} onChange={e => setO({ ...o, prix: e.target.value })} />
          <input className="champ champ-mono" placeholder="Frais (€) : auto" value={o.frais} onChange={e => setO({ ...o, frais: e.target.value })} />
        </div>
      )}
      {apercu && (
        <div className="info">
          <span>Frais estimés : courtage {euros(apercu.courtage)}{apercu.ttf > 0 ? ` + TTF ${euros(apercu.ttf)} (${pct(apercu.taux_ttf)})` : ''} = <b>{euros(apercu.total)}</b>
            {o.type === 'achat' && !apercu.ttf_applicable && <span className="discret"> · pas de TTF (titre étranger, ETF ou moins d'un milliard)</span>}</span>
        </div>
      )}
      {o.type === 'division' && <input className="champ champ-mono" placeholder="Ratio (2 pour une division par 2, 1,1 pour 1 gratuite pour 10)" value={o.quantite} onChange={e => setO({ ...o, quantite: e.target.value })} />}
      {['dividende', 'depot', 'retrait', 'frais'].includes(o.type) && <input className="champ champ-mono" placeholder="Montant en euros" value={o.montant} onChange={e => setO({ ...o, montant: e.target.value })} />}
      {['achat', 'vente'].includes(o.type) && <input className="champ champ-mono" placeholder="Montant net en euros (facultatif : sinon calculé au taux du jour)" value={o.montant} onChange={e => setO({ ...o, montant: e.target.value })} />}
      {erreur && <div className="erreur">{erreur}</div>}
    </Modale>
  )
}

function ModaleReleve({ comptes, compteId, onFermer }) {
  const [compte, setCompte] = useState(compteId || comptes[0]?.id)
  const [proposition, setProposition] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const lire = async f => {
    setOccupe(true); setErreur(null)
    try { setProposition(await api.portefeuille.lireReleve(compte, f)) } catch (e) { setErreur(e.message) } finally { setOccupe(false) }
  }
  const valider = async () => {
    setOccupe(true)
    try { onFermer((await api.portefeuille.validerReleve(compte, proposition.lignes.filter(l => l.garde !== false))).message) }
    catch (e) { setErreur(e.message); setOccupe(false) }
  }
  const modifier = (i, champ, v) => setProposition({ ...proposition, lignes: proposition.lignes.map((l, j) => j === i ? { ...l, [champ]: v } : l) })
  return (
    <Modale titre="Importer un relevé de courtier" large onFermer={() => onFermer()}
            pied={proposition && <><button className="btn" onClick={() => onFermer()}>Annuler</button><button className="btn btn-primaire" onClick={valider} disabled={occupe}>Importer les lignes cochées</button></>}>
      <select className="champ" value={compte} onChange={e => setCompte(e.target.value)}>{comptes.map(c => <option key={c.id} value={c.id}>{c.nom}</option>)}</select>
      {!proposition && (
        <>
          <div className="discret" style={{ fontSize: 12.5 }}>
            Exportez l'historique des opérations depuis le site de votre courtier (Boursorama, Degiro, Fortuneo, Trade Republic, Bourse Direct…)
            au format CSV. Les colonnes et le type d'opération sont reconnus automatiquement ; vous relisez tout avant l'import.
          </div>
          <DepotFichier onFichier={lire} occupe={occupe} />
        </>
      )}
      {proposition && (
        <div className="tableau-conteneur">
          <table className="tableau">
            <thead><tr><th /><th>Date</th><th style={{ textAlign: 'left' }}>Type</th><th style={{ textAlign: 'left' }}>Libellé</th><th style={{ textAlign: 'left' }}>Valeur</th><th>Qté</th><th>Prix</th><th>Frais</th><th>Montant €</th></tr></thead>
            <tbody>
              {proposition.lignes.map((l, i) => (
                <tr key={i} style={{ opacity: l.garde === false ? 0.4 : 1 }}>
                  <td><input type="checkbox" checked={l.garde !== false} onChange={e => modifier(i, 'garde', e.target.checked)} /></td>
                  <td style={{ textAlign: 'left' }}>{date(l.jour)}</td>
                  <td className="texte">
                    <select className="champ" style={{ padding: '2px 4px', width: 'auto' }} value={l.type ?? ''} onChange={e => modifier(i, 'type', e.target.value || null)}>
                      <option value="">— ignorer —</option>{Object.entries(TYPES_OP).map(([k, x]) => <option key={k} value={k}>{x}</option>)}
                    </select>
                  </td>
                  <td className="texte muet" style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }} title={l.libelle}>{l.libelle}</td>
                  <td className="texte">{l.valeur_nom ?? (l.suggestion ? <span title="sera ajoutée à vos valeurs">+ {l.suggestion.nom}</span> : <span className="muet">{l.isin ?? '—'}</span>)}</td>
                  <td>{l.quantite ?? '—'}</td><td>{l.prix ?? '—'}</td><td>{l.frais || '—'}</td><td>{l.montant ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {erreur && <div className="erreur">{erreur}</div>}
    </Modale>
  )
}
