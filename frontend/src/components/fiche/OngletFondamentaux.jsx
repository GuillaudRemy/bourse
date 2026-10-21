import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { pct, nombre, grand } from '../../lib/format'
import { useChamps, ETATS, SOURCES } from '../../lib/champs'
import DepotFichier from '../DepotFichier'
import Barres from '../Barres'
import RelecturePdf from '../RelecturePdf'
import { Stat } from './OngletRegression'

const INFOS = [
  ['per',                    'PER (12 derniers mois)', v => nombre(v, 1)],
  ['per_previsionnel',       'PER prévisionnel',       v => nombre(v, 1)],
  ['bpa',                    'BPA (12 derniers mois)', v => nombre(v, 2)],
  ['rendement',              'Rendement du dividende', v => nombre(v, 2) + ' %'],
  ['capitalisation',         'Capitalisation',         grand],
  ['valeur_entreprise',      "Valeur d'entreprise",    grand],
  ['cours_valeur_comptable', 'Cours / valeur comptable', v => nombre(v, 2)],
  ['roe',                    'Rentabilité des capitaux (ROE)', v => pct(v)],
  ['marge_nette',            'Marge nette',            v => pct(v)],
  ['dette_capitaux',         'Dette / capitaux propres', v => nombre(v, 0) + ' %'],
  ['beta',                   'Bêta',                   v => nombre(v, 2)],
]

const EXEMPLE = `Poste\t2005\t2006\t2007
Chiffre d'affaires\t10 400\t10 949\t11 801
Bénéfice net\t933\t1 002\t1 123
BPA dilué\t1,85\t2,05\t2,32`

/** « 3,5 Md », « 1 200 M », « 2.4e9 », « 1,85 » -> nombre ; vide -> null. */
function lire(texte) {
  const t = String(texte).trim().replace(/\s/g, '').replace(',', '.')
  if (!t) return null
  const m = t.match(/^(-?[\d.]+(?:e-?\d+)?)(k|m|md|g|b|t)?$/i)
  if (!m) return NaN
  const mult = { k: 1e3, m: 1e6, md: 1e9, g: 1e9, b: 1e9, t: 1e12 }[m[2]?.toLowerCase()] ?? 1
  return parseFloat(m[1]) * mult
}

const formater = (valeur, unite) =>
  valeur === null || valeur === undefined ? '' : unite === 'par_action' ? nombre(valeur, 2) : grand(valeur)

export default function OngletFondamentaux({ analyse, recharger }) {
  const { valeur, fondamentaux, fiabilite } = analyse
  const champs = useChamps()
  const [etat, setEtat] = useState('resultat')
  const [selection, setSelection] = useState('chiffre_affaires')
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [nouvelleAnnee, setNouvelleAnnee] = useState('')
  const [collage, setCollage] = useState('')
  const [proposition, setProposition] = useState(null)
  const defilement = useRef(null)

  const per = fiabilite?.verifications.find(v => v.cle === 'per')?.details ?? {}
  const infos = Object.entries(valeur.infos || {})
  const postes = champs.filter(c => c.etat === etat)
  const parAnnee = useMemo(() => Object.fromEntries(fondamentaux.map(f => [f.annee, f])), [fondamentaux])
  // Seules les annees qui ont au moins un chiffre dans l'etat affiche (pas de colonnes vides).
  const annees = fondamentaux
    .filter(f => !postes.length || postes.some(p => f[p.cle] !== null && f[p.cle] !== undefined) || Object.keys(f.sources || {}).length === 0)
    .map(f => f.annee)
  const poste = champs.find(c => c.cle === selection)

  // Les annees les plus recentes sont a droite : on y place la vue.
  useEffect(() => {
    if (defilement.current) defilement.current.scrollLeft = defilement.current.scrollWidth
  }, [etat, fondamentaux.length, champs.length])

  const action = async (fn, succes) => {
    setOccupe(true); setErreur(null); setInfo(null)
    try { const r = await fn(); if (succes) setInfo(succes(r)); await recharger() }
    catch (e) { setErreur(e.message) }
    finally { setOccupe(false) }
  }

  const ecrire = (annee, cle, v) => action(() => api.fondamentaux.ecrire(valeur.id, annee, { [cle]: v }))
  const ajouterAnnee = e => {
    e.preventDefault()
    const annee = parseInt(nouvelleAnnee, 10)
    if (annee) action(() => api.fondamentaux.ecrire(valeur.id, annee, {})).then(() => setNouvelleAnnee(''))
  }
  const supprimer = annee => {
    if (confirm(`Supprimer toute l'année ${annee} ?`)) action(() => api.fondamentaux.remove(valeur.id, annee))
  }

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat aide="bpa" libelle="Croissance du BPA" valeur={pct(per.croissance_bpa, { signe: true })} detail={per.annees ? `par an, sur ${per.annees} ans` : 'BPA à compléter'} />
        <Stat aide="renotation" libelle="Dérive du PER" valeur={pct(per.derive_per, { signe: true })} detail="par an — idéalement proche de 0" />
        <Stat aide="per" libelle="PER actuel / médian" valeur={per.per_actuel ? `${nombre(per.per_actuel, 1)} / ${nombre(per.per_median, 1)}` : '—'}
              detail="cours ÷ dernier BPA connu" />
        <Stat libelle="Pente de la droite" valeur={pct(analyse.regression?.pente, { signe: true })} detail="à comparer à la croissance du BPA" />
      </div>

      <div className="carte">
        <div className="graphique-barre">
          <div className="segments">
            {ETATS.map(e => (
              <button key={e.cle} className={`segment${etat === e.cle ? ' actif' : ''}`} onClick={() => setEtat(e.cle)}>
                {e.libelle}
              </button>
            ))}
          </div>
          <span className="espaceur" />
          <span className="legende-sources">
            <span><i className="src-officiel" /> Officiel (SEC, ESEF)</span>
            <span><i className="src-manuel" /> Saisie / import</span>
            <span><i className="src-yahoo" /> Yahoo</span>
          </span>
        </div>

        {poste && poste.etat === etat && (
          <div className="carte-corps" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="discret" style={{ marginBottom: 6 }}>{poste.libelle}{valeur.devise_comptes && poste.unite !== 'nombre' ? ` (${valeur.devise_comptes})` : ''}</div>
            <Barres points={annees.map(a => ({ x: a, y: parAnnee[a]?.[poste.cle] }))}
                    format={v => formater(v, poste.unite)} />
          </div>
        )}

        {erreur && <div className="erreur" style={{ margin: 12 }}>{erreur}</div>}
        <div className="tableau-conteneur" ref={defilement}>
          <table className="tableau tableau-etats">
            <thead>
              <tr>
                <th>Poste — cliquez une case pour la modifier</th>
                {annees.map(a => (
                  <th key={a}>
                    {a} <button className="btn-annee" title={`Supprimer ${a}`} onClick={() => supprimer(a)}>×</button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {postes.map(p => (
                <tr key={p.cle} className={selection === p.cle ? 'ligne-choisie' : ''}>
                  <td className="texte">
                    <button className="lien-poste" onClick={() => setSelection(p.cle)} title={p.aide || 'Afficher le graphique'}>
                      {p.libelle}
                    </button>
                  </td>
                  {annees.map(a => {
                    const ligne = parAnnee[a]
                    const source = ligne.sources?.[p.cle]
                    const ajuste = ligne.ajustes?.includes(p.cle)
                    return (
                      <td key={a} className={SOURCES[source]?.classe ?? ''}
                          title={source ? `Source : ${SOURCES[source]?.libelle ?? source}${ajuste ? ' — ajusté des divisions d’actions' : ''}` : ''}>
                        <Cellule valeur={ligne[p.cle]} unite={p.unite} onChange={v => ecrire(a, p.cle, v)} />
                        {ajuste && <sup className="marque-ajuste">÷</sup>}
                      </td>
                    )
                  })}
                </tr>
              ))}
              {etat === 'action' && (
                <tr>
                  <td className="texte muet" title="Cours moyen de l'année ÷ BPA">PER moyen (calculé)</td>
                  {annees.map(a => <td key={a} className="muet">{nombre(parAnnee[a].per, 1)}</td>)}
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <form className="graphique-barre" style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }} onSubmit={ajouterAnnee}>
          <input className="champ" style={{ width: 110 }} placeholder="Année" inputMode="numeric"
                 value={nouvelleAnnee} onChange={e => setNouvelleAnnee(e.target.value)} />
          <button className="btn" disabled={!nouvelleAnnee || occupe}>Ajouter l'année</button>
          <span className="discret">
            Montants : 1,85 · 3,5 Md · 933 M. Saisissez les chiffres tels que publiés : les BPA sont ajustés
            automatiquement des divisions d'actions ultérieures (÷).
          </span>
        </form>
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Coller depuis un tableur</div>
          <div className="carte-corps pile">
            <div className="discret" style={{ fontSize: 12.5 }}>
              Copiez un tableau dans Excel, LibreOffice ou Google Sheets (une ligne par poste et les années en
              colonnes, ou l'inverse) et collez-le ici. Idéal pour saisir 20 ans d'un coup depuis un rapport annuel.
            </div>
            <textarea className="champ champ-mono" rows={6} placeholder={EXEMPLE} value={collage}
                      onChange={e => setCollage(e.target.value)} />
            <div className="rangee">
              <button className="btn btn-primaire" disabled={!collage.trim() || occupe}
                      onClick={() => action(() => api.imports.coller(valeur.id, collage), r => { setCollage(''); return r.message })}>
                Importer le tableau collé
              </button>
              <span className="espaceur" />
              <span className="discret">ou</span>
            </div>
            <DepotFichier onFichier={f => action(() => api.imports.fondamentaux(valeur.id, f), r => r.message)} occupe={occupe}
                          libelle="Déposer un fichier CSV" />
            <DepotFichier onFichier={f => action(async () => setProposition(await api.imports.pdf(valeur.id, f)))}
                          occupe={occupe} accept=".pdf,application/pdf"
                          libelle="Rapport annuel PDF : extraction assistée, à relire avant enregistrement" />
            {info && <div className="succes">{info}</div>}
          </div>
        </div>

        {infos.length > 0 && (
          <div className="carte">
            <div className="section-titre">Ratios actuels (Yahoo)</div>
            <dl className="liste-cle">
              {INFOS.filter(([cle]) => valeur.infos[cle] !== undefined).map(([cle, libelle, f]) => (
                <div key={cle}><dt>{libelle}</dt><dd>{f(valeur.infos[cle])}</dd></div>
              ))}
            </dl>
          </div>
        )}
      </div>
      {proposition && (
        <RelecturePdf
          proposition={proposition}
          onFermer={() => setProposition(null)}
          onValider={annees => action(() => api.imports.lot(valeur.id, annees), r => { setProposition(null); return r.message })}
        />
      )}
    </div>
  )
}

function Cellule({ valeur, unite, onChange }) {
  const [edition, setEdition] = useState(null)   // texte en cours de saisie, ou null
  const vide = valeur === null || valeur === undefined

  const valider = () => {
    if (edition === null) return
    const n = lire(edition)
    setEdition(null)
    if (Number.isNaN(n) || n === valeur || (n === null && vide)) return
    onChange(n)
  }

  return (
    <input
      className="champ-cellule"
      value={edition ?? formater(valeur, unite)}
      placeholder="—"
      onFocus={() => setEdition(vide ? '' : String(valeur).replace('.', ','))}
      onChange={e => setEdition(e.target.value)}
      onBlur={valider}
      onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') { setEdition(null); e.currentTarget.blur() } }}
    />
  )
}
