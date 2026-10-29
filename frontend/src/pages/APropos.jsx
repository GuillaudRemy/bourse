// @ts-check
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { date } from '../lib/format'
import Sauvegardes from '../components/Sauvegardes'

const taille = o => o > 1e6 ? `${(o / 1e6).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Mo` : `${Math.round(o / 1e3)} ko`

export default function APropos() {
  const [infos, setInfos] = useState(null)
  const [erreur, setErreur] = useState(null)
  useEffect(() => { api.systeme.aPropos().then(setInfos).catch(e => setErreur(e.message)) }, [])
  if (erreur) return <div className="page"><div className="erreur">{erreur}</div></div>
  if (!infos) return <div className="page"><div className="chargement">Chargement…</div></div>
  const lignes = [
    ['Version', infos.version], ['Système', infos.systeme], ['Python', infos.python],
    ['Dernière actualisation', infos.derniere_actualisation ? date(infos.derniere_actualisation) : 'jamais'],
    ['Base de données', `${infos.base} (${taille(infos.taille_base)})`],
    ['Sauvegardes', `${infos.sauvegardes} (${infos.nombre_sauvegardes})`], ['Journal', infos.journal],
    ['Réponses brutes des sources', infos.reponses_brutes && `${infos.reponses_brutes.dossier} (${infos.reponses_brutes.fichiers} fichiers, ${taille(infos.reponses_brutes.taille)}, gardées ${infos.reponses_brutes.jours} jours)`],
  ]
  return (
    <div className="page">
      <div className="page-entete">
        <div>
          <h1 className="page-titre">À propos</h1>
          <div className="page-sous-titre">Bourse — analyse d'actions sur le long terme, logiciel libre</div>
        </div>
        <div className="rangee">
          <a className="btn" href={infos.depot} target="_blank" rel="noreferrer">Code source</a>
          <a className="btn btn-primaire" href="/api/diagnostic.zip">Télécharger le diagnostic</a>
        </div>
      </div>
      <div className="grille-2" style={{ alignItems: 'start' }}>
        <div className="carte">
          <div className="section-titre">Installation</div>
          <dl className="liste-cle">
            {lignes.map(([cle, val]) => <div key={cle}><dt>{cle}</dt><dd style={{ wordBreak: 'break-all' }}>{val}</dd></div>)}
          </dl>
          <p className="discret" style={{ padding: '12px 16px' }}>
            En cas de problème, le <b>diagnostic</b> est un fichier .zip à envoyer à la personne qui vous aide :
            il contient le journal de l'application, les versions et le nombre d'enregistrements par table.
            Il ne contient <b>ni vos cours, ni vos comptes, ni votre portefeuille</b>, ni mots de passe ou adresses e-mail.
          </p>
        </div>
        <div className="carte">
          <div className="section-titre">Contenu de la base (tables non vides)</div>
          <dl className="liste-cle">
            {Object.entries(infos.enregistrements).filter(([t, n]) => t !== 'alembic_version' && n > 0).map(([t, n]) =>
              <div key={t}><dt>{t}</dt><dd>{n.toLocaleString('fr-FR')}</dd></div>)}
          </dl>
          <div className="section-titre">Bibliothèques</div>
          <dl className="liste-cle">
            {Object.entries(infos.bibliotheques).map(([nom, v]) => <div key={nom}><dt>{nom}</dt><dd>{v ?? '—'}</dd></div>)}
          </dl>
        </div>
      </div>
      <Sauvegardes />
      <div className="carte prose" style={{ marginTop: 20, padding: '14px 18px' }}>
        <div className="section-titre" style={{ padding: 0, border: 'none' }}>Mentions</div>
        <p><b>Pas un conseil en investissement.</b> Bourse est un outil d'aide à l'analyse. Ses calculs (droite de régression,
          scores, valorisations, projections, backtests) reposent sur le passé et sur des hypothèses ; ils peuvent être faux
          et ne garantissent rien. Toute décision d'investissement reste la vôtre. Investir en actions expose à une perte en capital.</p>
        <p><b>Sources de données.</b> Cours et ratios : Yahoo Finance, dont les données sont destinées à un usage personnel
          et non commercial. Comptes : SEC EDGAR (domaine public) et filings.xbrl.org (rapports ESEF). Taux de change :
          Banque centrale européenne. Compositions d'indices : Wikipédia (CC BY-SA). Actualités : Google Actualités.
          Les données peuvent comporter des erreurs ou des retards.</p>
        <p><b>Fiscalité.</b> Les estimations fiscales suivent les règles publiées sur service-public.fr ; elles ne remplacent
          pas votre déclaration ni l'avis d'un professionnel.</p>
        <p><b>Vos données</b> restent sur cet ordinateur. L'application ne contacte que les sources ci-dessus et GitHub
          (mises à jour).</p>
      </div>
    </div>
  )
}
