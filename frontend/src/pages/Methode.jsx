// @ts-check
import { ZONES } from '../lib/zones'

export default function Methode() {
  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">La méthode</h1>
          <div className="page-sous-titre">Droite de régression, couloir d'écarts-types, et les trois vérifications</div>
        </div>
        <div className="rangee">
          <a className="btn" href="/glossaire">Glossaire</a>
          <button className="btn" onClick={() => window.dispatchEvent(new Event('revoir-bienvenue'))}>Revoir la visite guidée</button>
        </div>
      </div>

      <div className="prose">
        <p>
          La bourse est un <b>système complexe</b> : imprévisible dans le détail, au jour le jour,
          mais remarquablement ordonnée dans l'agrégat, sur la durée. Sur le long terme, le cours d'une
          action suit approximativement une <b>loi log-normale</b> (Bachelier 1900, Samuelson, Black-Scholes) :
          en échelle logarithmique, il oscille autour d'une droite, et les écarts à cette droite se
          répartissent en cloche.
        </p>

        <h2>Ce que montre la droite</h2>
        <ul>
          <li><b>Échelle logarithmique</b> : ce qui compte pour l'investisseur, ce sont les variations en pourcentage, pas en euros.</li>
          <li><b>Dividendes réinvestis</b> : le cours est celui du rendement total, pour ne pas pénaliser les sociétés qui distribuent beaucoup.</li>
          <li><b>La pente</b> est le rythme de croisière de l'action : sa performance moyenne par an.</li>
          <li><b>L'écart-type</b> est la largeur du couloir : faible pour une valeur « de père de famille », large pour une valeur cyclique.</li>
        </ul>

        <h2>Les zones du couloir</h2>
        <div className="carte">
          <dl className="liste-cle">
            {[
              ['surevaluation_manifeste', '≈ 2,5 % du temps — jouer contre les probabilités'],
              ['surevalue', '≈ 13,5 % — commence à être cher'],
              ['normal', '≈ 68 % — le cours respire autour de sa tendance'],
              ['sous_evalue', '≈ 13,5 % — zone où se poser la question d’acheter'],
              ['opportunite_manifeste', '≈ 2,5 % — les belles occasions, 39 fois sur 40 un retour vers la droite'],
            ].map(([cle, texte]) => (
              <div key={cle}>
                <dt><span className={`badge ${ZONES[cle].classe}`}>{ZONES[cle].libelle}</span> <span className="mono discret">{ZONES[cle].court}</span></dt>
                <dd style={{ fontFamily: 'var(--f-body)', color: 'var(--muted)' }}>{texte}</dd>
              </div>
            ))}
          </dl>
        </div>
        <p className="discret">
          Dans la réalité, les extrêmes sont un peu plus fréquents que la théorie (« queues épaisses ») —
          mais il vaut mieux avoir vaguement raison que précisément tort.
        </p>

        <h2>Avant de prolonger la droite : trois vérifications</h2>
        <ol>
          <li>
            <b>Un historique assez long</b> — au moins 20 ans, pour avoir traversé plusieurs cycles.
            Départ par défaut : 2003 pour les actions (après la bulle internet, après l'entrée de la Chine
            à l'OMC), 1992 pour les indices (début du régime monétaire moderne).
          </li>
          <li>
            <b>Une pente portée par les bénéfices</b> — cours = bénéfice × PER. Si le PER est stable, la pente
            est la croissance des bénéfices : elle est reproductible. Si elle vient d'un PER qui a gonflé
            (renotation), elle ne se répétera pas. Un PER qui fait le yo-yo n'est pas un problème : sur
            20 ans, les allers-retours se compensent.
          </li>
          <li>
            <b>Une entreprise fidèle à elle-même</b> — pas de rupture qui aurait dopé ou cassé
            durablement les bénéfices (CGG devenu Viridien, Kodak, Solocal, Orpea devenu Emeis…).
            Ces ruptures sont rares : la plupart des entreprises restent fidèles à elles-mêmes.
          </li>
        </ol>

        <div className="regle-or">La droite donne le cadre, les comptes la valident.</div>

        <h2>Sources de données</h2>
        <p>
          Les cours, dividendes et ratios viennent de <b>Yahoo Finance</b> (bibliothèque libre <i>yfinance</i>,
          avec un accès direct de secours). Les comptes annuels viennent des sources officielles : la <b>SEC</b> pour
          les sociétés américaines (jusqu'à 20 ans) et les rapports <b>ESEF</b> pour les européennes (depuis 2020) ;
          les taux de change, de la <b>BCE</b>. Pour un historique plus long ou une valeur non couverte : import CSV,
          collage depuis un tableur ou rapport annuel PDF.
        </p>
        <p className="discret">
          Outil d'aide à l'analyse, pas un conseil en investissement.
        </p>
      </div>
    </div>
  )
}
