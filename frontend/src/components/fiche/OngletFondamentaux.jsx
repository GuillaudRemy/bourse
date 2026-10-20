import { useState } from 'react'
import { api } from '../../lib/api'
import { pct, nombre, grand } from '../../lib/format'
import DepotFichier from '../DepotFichier'
import { Stat } from './OngletRegression'

const CHAMPS = [
  { cle: 'bpa',              libelle: 'BPA',              grand: false },
  { cle: 'benefice_net',     libelle: 'Bénéfice net',     grand: true },
  { cle: 'chiffre_affaires', libelle: "Chiffre d'affaires", grand: true },
  { cle: 'dividende',        libelle: 'Dividende / action', grand: false },
]

const INFOS = [
  ['per',                    'PER (12 derniers mois)', v => nombre(v, 1)],
  ['per_previsionnel',       'PER prévisionnel',       v => nombre(v, 1)],
  ['bpa',                    'BPA (12 derniers mois)', v => nombre(v, 2)],
  ['rendement',              'Rendement du dividende', v => nombre(v, 2) + ' %'],
  ['capitalisation',         'Capitalisation',         grand],
  ['cours_valeur_comptable', 'Cours / valeur comptable', v => nombre(v, 2)],
  ['roe',                    'Rentabilité des capitaux (ROE)', v => pct(v)],
  ['marge_nette',            'Marge nette',            v => pct(v)],
  ['dette_capitaux',         'Dette / capitaux propres', v => nombre(v, 0) + ' %'],
  ['beta',                   'Bêta',                   v => nombre(v, 2)],
]

const EXEMPLE = `annee;bpa;benefice_net;chiffre_affaires;dividende
2005;1,85;933M;10 400M;0,75
2006;2,05;1 002M;10 949M;0,83
…`

/** « 3,5 Md », « 1 200 M », « 2.4e9 », « 1,85 » -> nombre ; vide -> null. */
function lire(texte) {
  const t = String(texte).trim().replace(/\s/g, '').replace(',', '.')
  if (!t) return null
  const m = t.match(/^(-?[\d.]+(?:e-?\d+)?)(k|m|md|g|b|t)?$/i)
  if (!m) return NaN
  const mult = { k: 1e3, m: 1e6, md: 1e9, g: 1e9, b: 1e9, t: 1e12 }[m[2]?.toLowerCase()] ?? 1
  return parseFloat(m[1]) * mult
}

export default function OngletFondamentaux({ analyse, recharger }) {
  const { valeur, fondamentaux, fiabilite } = analyse
  const [erreur, setErreur] = useState(null)
  const [info, setInfo] = useState(null)
  const [import_, setImport] = useState(false)
  const [nouvelleAnnee, setNouvelleAnnee] = useState('')

  const per = fiabilite?.verifications.find(v => v.cle === 'per')?.details ?? {}
  const infos = Object.entries(valeur.infos || {})

  const ecrire = async (ligne, cle, valeur_) => {
    const donnees = Object.fromEntries(CHAMPS.map(c => [c.cle, ligne[c.cle]]))
    donnees[cle] = valeur_
    setErreur(null)
    try { await api.fondamentaux.ecrire(valeur.id, ligne.annee, donnees); await recharger() }
    catch (e) { setErreur(e.message) }
  }

  const ajouterAnnee = async e => {
    e.preventDefault()
    const annee = parseInt(nouvelleAnnee, 10)
    if (!annee) return
    try { await api.fondamentaux.ecrire(valeur.id, annee, {}); setNouvelleAnnee(''); await recharger() }
    catch (e) { setErreur(e.message) }
  }

  const supprimer = async annee => {
    if (!confirm(`Supprimer l'année ${annee} ?`)) return
    try { await api.fondamentaux.remove(valeur.id, annee); await recharger() }
    catch (e) { setErreur(e.message) }
  }

  const importer = async fichier => {
    setImport(true); setErreur(null); setInfo(null)
    try { setInfo((await api.imports.fondamentaux(valeur.id, fichier)).message); await recharger() }
    catch (e) { setErreur(e.message) }
    finally { setImport(false) }
  }

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat libelle="Croissance du BPA" valeur={pct(per.croissance_bpa, { signe: true })} detail={per.annees ? `par an, sur ${per.annees} ans` : 'BPA à compléter'} />
        <Stat libelle="Dérive du PER" valeur={pct(per.derive_per, { signe: true })} detail="par an — idéalement proche de 0" />
        <Stat libelle="PER actuel / médian" valeur={per.per_actuel ? `${nombre(per.per_actuel, 1)} / ${nombre(per.per_median, 1)}` : '—'}
              detail="cours ÷ dernier BPA connu" />
        <Stat libelle="Pente de la droite" valeur={pct(analyse.regression?.pente, { signe: true })} detail="à comparer à la croissance du BPA" />
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="section-titre">Données annuelles — cliquez une case pour la modifier</div>
          {erreur && <div className="erreur" style={{ margin: 12 }}>{erreur}</div>}
          <div className="tableau-conteneur">
            <table className="tableau">
              <thead>
                <tr>
                  <th>Année</th>
                  {CHAMPS.map(c => <th key={c.cle}>{c.libelle}</th>)}
                  <th title="Cours moyen de l'année ÷ BPA">PER moyen</th>
                  <th>Source</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {[...fondamentaux].reverse().map(l => (
                  <tr key={l.annee}>
                    <td className="mono">{l.annee}</td>
                    {CHAMPS.map(c => (
                      <td key={c.cle}>
                        <Cellule valeur={l[c.cle]} grand={c.grand} onChange={v => ecrire(l, c.cle, v)} />
                      </td>
                    ))}
                    <td>{nombre(l.per, 1)}</td>
                    <td className="texte"><span className="etiquette">{l.source}</span></td>
                    <td><button className="btn btn-mini btn-fantome" onClick={() => supprimer(l.annee)}>×</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <form className="graphique-barre" style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }} onSubmit={ajouterAnnee}>
            <input className="champ" style={{ width: 110 }} placeholder="Année" inputMode="numeric"
                   value={nouvelleAnnee} onChange={e => setNouvelleAnnee(e.target.value)} />
            <button className="btn" disabled={!nouvelleAnnee}>Ajouter l'année</button>
            <span className="discret">Montants acceptés : 1,85 · 3,5 Md · 933 M</span>
          </form>
        </div>

        <div className="pile" style={{ gap: 16 }}>
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
          <div className="carte">
            <div className="section-titre">Importer un historique</div>
            <div className="carte-corps pile">
              <div className="discret" style={{ fontSize: 12.5 }}>
                Yahoo ne fournit les comptes que sur 4–5 ans. Pour vérifier que la pente est portée
                par les bénéfices, il faut idéalement 20 ans de BPA : importez-les (rapports annuels,
                Boursorama, Zonebourse…). Les lignes importées ou saisies ne sont jamais écrasées par Yahoo.
              </div>
              <div className="code">{EXEMPLE}</div>
              <DepotFichier onFichier={importer} occupe={import_} />
              {info && <div className="succes">{info}</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Cellule({ valeur, grand: estGrand, onChange }) {
  const [edition, setEdition] = useState(null)   // texte en cours de saisie, ou null
  const affiche = valeur === null || valeur === undefined ? '' : estGrand ? grand(valeur) : nombre(valeur, 2)

  const valider = () => {
    if (edition === null) return
    const n = lire(edition)
    setEdition(null)
    if (Number.isNaN(n) || n === valeur || (n === null && (valeur === null || valeur === undefined))) return
    onChange(n)
  }

  return (
    <input
      className="champ-cellule"
      value={edition ?? affiche}
      placeholder="—"
      onFocus={() => setEdition(valeur === null || valeur === undefined ? '' : String(valeur).replace('.', ','))}
      onChange={e => setEdition(e.target.value)}
      onBlur={valider}
      onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur(); if (e.key === 'Escape') { setEdition(null); e.currentTarget.blur() } }}
    />
  )
}
