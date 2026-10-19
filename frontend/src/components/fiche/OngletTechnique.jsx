import { useState } from 'react'
import { pct, prix, nombre, date, ton } from '../../lib/format'
import GraphiqueTechnique from '../GraphiqueTechnique'
import { Stat } from './OngletRegression'

const CLE_OPTIONS = 'bourse.options-techniques'
const DEFAUT = { bougies: true, log: false, mm20: true, mm50: true, mm200: true, bollinger: false, volume: true, rsi: true, macd: true }

function lireOptions() {
  try { return { ...DEFAUT, ...JSON.parse(localStorage.getItem(CLE_OPTIONS) || '{}') } }
  catch { return DEFAUT }
}

const LIBELLES = {
  bougies: 'Bougies', log: 'Log', mm20: 'MM20', mm50: 'MM50', mm200: 'MM200',
  bollinger: 'Bollinger', volume: 'Volume', rsi: 'RSI', macd: 'MACD',
}

export default function OngletTechnique({ analyse }) {
  const [options, setOptions] = useState(lireOptions)
  const { stats, signaux, valeur } = analyse
  const devise = valeur.devise

  const basculer = cle => {
    const suivantes = { ...options, [cle]: !options[cle] }
    setOptions(suivantes)
    try { localStorage.setItem(CLE_OPTIONS, JSON.stringify(suivantes)) } catch { /* stockage indisponible */ }
  }

  return (
    <div className="pile" style={{ gap: 16 }}>
      <div className="stat-grille">
        <Stat libelle="RSI 14" valeur={nombre(stats.rsi, 0)}
              classe={stats.rsi >= 70 ? 'negatif' : stats.rsi <= 30 ? 'positif' : ''}
              detail={stats.rsi >= 70 ? 'surachat' : stats.rsi <= 30 ? 'survente' : 'neutre'} />
        <Stat libelle="Écart à la MM200" valeur={pct(stats.ecart_mm200, { signe: true })} classe={ton(stats.ecart_mm200)}
              detail={`MM200 à ${prix(stats.mm200, devise)}`} />
        <Stat libelle="Volatilité (1 an)" valeur={pct(stats.volatilite, { decimales: 0 })} detail="annualisée" />
        <Stat libelle="Perte maximale" valeur={pct(stats.perte_max?.baisse)} classe="negatif"
              detail={stats.perte_max && `${date(stats.perte_max.sommet)} → ${date(stats.perte_max.creux)}`} />
        <Stat libelle="Depuis le 1er janvier" valeur={pct(stats.perf_ytd, { signe: true })} classe={ton(stats.perf_ytd)} />
        <Stat libelle="1 an / 5 ans" valeur={pct(stats.perf_1an, { signe: true })} classe={ton(stats.perf_1an)}
              detail={`5 ans : ${pct(stats.perf_5ans, { signe: true })}`} />
      </div>

      <div className="grille-2">
        <div className="carte">
          <div className="graphique-barre">
            {Object.keys(LIBELLES).map(cle => (
              <label key={cle} className="interrupteur">
                <input type="checkbox" checked={options[cle]} onChange={() => basculer(cle)} />
                {LIBELLES[cle]}
              </label>
            ))}
          </div>
          <GraphiqueTechnique analyse={analyse} options={options} />
        </div>

        <div className="pile" style={{ gap: 16 }}>
          <div className="carte">
            <div className="section-titre">Signaux</div>
            {signaux.map((s, i) => (
              <div key={i} className="signal">
                <span className={`signal-point ${s.ton}`} />
                {s.texte}
              </div>
            ))}
          </div>
          <div className="carte">
            <div className="section-titre">Repères</div>
            <dl className="liste-cle">
              <div><dt>MM50</dt><dd>{prix(stats.mm50, devise)}</dd></div>
              <div><dt>MM200</dt><dd>{prix(stats.mm200, devise)}</dd></div>
              <div><dt>Plus haut 52 semaines</dt><dd>{prix(stats.plus_haut_52s, devise)}</dd></div>
              <div><dt>Plus bas 52 semaines</dt><dd>{prix(stats.plus_bas_52s, devise)}</dd></div>
              <div><dt>Performance annualisée</dt><dd>{pct(stats.perf_annuelle, { signe: true })}</dd></div>
              <div><dt>Historique depuis</dt><dd>{date(stats.premier_jour)}</dd></div>
            </dl>
          </div>
          <div className="discret">
            Les indicateurs techniques lisent le court terme. Pour un investisseur de long terme,
            ils aident à choisir le moment d'entrée une fois la valeur sélectionnée par sa droite et ses comptes.
          </div>
        </div>
      </div>
    </div>
  )
}
