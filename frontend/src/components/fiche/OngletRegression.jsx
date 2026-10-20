import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { pct, prix, nombre, sigma, date } from '../../lib/format'
import { ZONES, ORDRE_ZONES, STATUTS } from '../../lib/zones'
import Jauge, { BadgeZone } from '../Jauge'
import GraphiqueRegression from '../GraphiqueRegression'

const ICONES = { ok: '✓', inconnu: '?', attention: '!', alerte: '✕' }
const COULEURS_ZONES = {
  opportunite_manifeste: 'var(--z-om)', sous_evalue: 'var(--z-se)', normal: '#9CA3AF',
  surevalue: 'var(--z-sv)', surevaluation_manifeste: 'var(--z-sm)',
}

export default function OngletRegression({ analyse, dividendes, setDividendes, debut, setDebut, enEuros, setEnEuros }) {
  const [log, setLog] = useState(true)
  const { regression: reg, valeur, fiabilite, base_ajustee } = analyse
  if (!reg) return <div className="carte vide">Pas assez de cours pour tracer une droite (30 séances minimum).</div>

  const devise = analyse.devise_affichee

  return (
    <div className="pile" style={{ gap: 16 }}>
      {analyse.avertissement_indice && <AvertissementIndice avertissement={analyse.avertissement_indice} />}
      <div className="stat-grille">
        <Stat libelle="Pente (rythme de croisière)" valeur={pct(reg.pente, { signe: true })} classe={reg.pente >= 0 ? 'positif' : 'negatif'}
              detail={base_ajustee ? 'par an, dividendes réinvestis' : 'par an, hors dividendes'} />
        <Stat libelle="Écart-type (largeur du couloir)" valeur={pct(reg.ecart_type, { decimales: 0 })}
              detail={reg.ecart_type < 0.15 ? 'action calme' : reg.ecart_type < 0.4 ? 'volatilité moyenne' : 'action nerveuse'} />
        <Stat libelle="Position dans le couloir" valeur={sigma(reg.position)} detail={<BadgeZone zone={reg.zone} />} />
        <Stat libelle="Retour à la droite" valeur={pct(reg.retour_droite, { signe: true })} classe={reg.retour_droite >= 0 ? 'positif' : 'negatif'}
              detail={`droite à ${prix(reg.valeur_droite, devise)}`} />
        <Stat libelle="Période analysée" valeur={`${nombre(reg.annees, 1)} ans`} detail={`${date(reg.debut)} → ${date(reg.fin)}`} />
        <Stat libelle="R² (qualité de l'ajustement)" valeur={nombre(reg.r2, 2)} detail="1 = droite parfaite" />
      </div>

      <div className="grille-2">
        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="graphique-barre">
              <label className="interrupteur">
                <input type="checkbox" checked={log} onChange={e => setLog(e.target.checked)} />
                Échelle logarithmique
              </label>
              <label className="interrupteur" title="Rendement total : le dividende est réinvesti dans l'action le jour de son versement.">
                <input type="checkbox" checked={dividendes} onChange={e => setDividendes(e.target.checked)} />
                Dividendes réinvestis
              </label>
              <InterrupteurEuros valeur={valeur} enEuros={enEuros} setEnEuros={setEnEuros} />
              <span className="espaceur" />
              <label className="interrupteur">
                Début
                <input
                  type="date" className="champ" style={{ width: 150, padding: '4px 8px' }}
                  value={debut || valeur.debut_regression || analyse.debut_defaut}
                  onChange={e => setDebut(e.target.value)}
                />
              </label>
              {debut && <button className="btn btn-mini btn-fantome" onClick={() => setDebut('')}>Réinitialiser</button>}
            </div>
            {dividendes && !base_ajustee && (
              <div className="info" style={{ margin: '10px 14px 0' }}>
                Pas de cours « dividendes réinvestis » pour cette valeur : la droite est tracée sur la clôture.
              </div>
            )}
            <GraphiqueRegression analyse={analyse} log={log} />
          </div>

          <div className="carte">
            <div className="section-titre">Temps passé dans chaque zone — observé (barre) vs loi normale (trait)</div>
            <div className="repartition">
              {[...ORDRE_ZONES].reverse().map(cle => (
                <div key={cle} className="repartition-ligne">
                  <span><BadgeZone zone={cle} /></span>
                  <div className="repartition-barres">
                    <div className="repartition-obs" style={{ width: `${reg.repartition[cle] * 100}%`, background: COULEURS_ZONES[cle] }} />
                    <div className="repartition-theo" style={{ left: `${reg.theorie[cle] * 100}%` }} />
                  </div>
                  <span className="mono" style={{ textAlign: 'right' }}>{pct(reg.repartition[cle], { decimales: 0 })}</span>
                </div>
              ))}
              <div className="discret">
                Théorie : 68 % du temps entre −1σ et +1σ, 27 % entre 1σ et 2σ, 5 % au-delà de 2σ.
                Dans la réalité, les extrêmes sont un peu plus fréquents (« queues épaisses »).
              </div>
            </div>
          </div>
        </div>

        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Où en est le cours ?</div>
            <div className="carte-corps pile">
              <Jauge position={reg.position} grande />
              <div className="discret" style={{ fontSize: 12.5 }}>
                {texteZone(reg.zone)}
              </div>
            </div>
            <dl className="liste-cle" style={{ borderTop: '1px solid var(--border)' }}>
              <div><dt>Cours actuel</dt><dd>{prix(reg.dernier, devise)}</dd></div>
              <div><dt>Valeur sur la droite</dt><dd>{prix(reg.valeur_droite, devise)}</dd></div>
              {reg.projections.map(p => (
                <div key={p.ans}><dt>Droite dans {p.ans} an{p.ans > 1 ? 's' : ''}</dt><dd>{prix(p.valeur, devise)}</dd></div>
              ))}
            </dl>
          </div>

          {fiabilite && (
            <div className="carte">
              <div className="section-titre">Peut-on prolonger la droite ?</div>
              <div className={`verdict ${STATUTS[fiabilite.verdict.statut].classe}`}>{fiabilite.verdict.texte}</div>
              {fiabilite.verifications.map(v => (
                <div key={v.cle} className="verif">
                  <span className={`verif-icone ${STATUTS[v.statut].classe}`}>{ICONES[v.statut]}</span>
                  <div>
                    <div className="verif-titre">{v.titre}</div>
                    <div className="verif-texte">{v.texte}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="regle-or">La droite donne le cadre, les comptes la valident.</div>
        </div>
      </div>
    </div>
  )
}

export function InterrupteurEuros({ valeur, enEuros, setEnEuros }) {
  if (!valeur.devise || valeur.devise === 'EUR') return null
  return (
    <label className="interrupteur" title="Cours convertis au taux de référence BCE du jour : la pente inclut l'effet de change, comme pour un investisseur en euros.">
      <input type="checkbox" checked={enEuros} onChange={e => setEnEuros(e.target.checked)} />
      En euros
    </label>
  )
}

function AvertissementIndice({ avertissement }) {
  const naviguer = useNavigate()
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState(null)
  const suivre = async () => {
    setOccupe(true)
    try {
      const existantes = await api.valeurs.list()
      const deja = existantes.find(v => v.symbole === avertissement.symbole)
      const valeur = deja ?? await api.valeurs.create({ symbole: avertissement.symbole, source: 'yahoo' })
      naviguer(`/valeurs/${valeur.id}`)
    } catch (e) { setErreur(e.message) } finally { setOccupe(false) }
  }
  return (
    <div className="info" style={{ background: '#FFF7ED', color: '#9A3412', borderColor: '#FED7AA' }}>
      <span>{erreur || avertissement.texte}</span>
      {avertissement.symbole && (
        <button className="btn btn-mini" onClick={suivre} disabled={occupe}>
          {occupe ? 'Téléchargement…' : `Ouvrir ${avertissement.nom}`}
        </button>
      )}
    </div>
  )
}

function texteZone(zone) {
  return {
    opportunite_manifeste: 'Tout en bas du couloir : situation rare (≈ 1 fois sur 40). Les probabilités penchent fortement pour un retour vers la droite — si l’entreprise n’a pas changé de nature.',
    sous_evalue: 'Sous la tendance : zone où l’on peut se poser la question d’acheter ou de renforcer.',
    normal: 'Le cours respire autour de sa tendance de fond, comme deux tiers du temps.',
    surevalue: 'Au-dessus de la tendance : le cours commence à être cher par rapport à son historique.',
    surevaluation_manifeste: 'Tout en haut du couloir : acheter ici, c’est jouer contre les probabilités. Un investisseur prudent allège ou s’abstient.',
  }[zone] ?? ZONES[zone]?.libelle
}

export function Stat({ libelle, valeur, detail, classe = '' }) {
  return (
    <div className="carte stat">
      <div className={`stat-valeur ${classe}`}>{valeur}</div>
      <div className="stat-libelle">{libelle}</div>
      {detail && <div className="stat-detail">{detail}</div>}
    </div>
  )
}
