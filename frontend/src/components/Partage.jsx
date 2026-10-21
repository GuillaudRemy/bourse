// @ts-check
import { useState } from 'react'
import { api } from '../lib/api'

const LIBELLES = [['valeurs', 'valeur(s)'], ['theses', 'thèse(s)'], ['decisions', 'décision(s)'], ['annotations', 'tracé(s)'],
  ['alertes', 'alerte(s)'], ['annees_comptes_saisis', 'année(s) de comptes saisis'], ['comptes_saisis', 'case(s) de comptes saisis'],
  ['listes', 'liste(s)'], ['filtres', 'filtre(s)'], ['comptes', 'compte(s)'], ['transactions', 'opération(s)']]

/** Partage avec un autre PC : un fichier .bourse.json a envoyer par e-mail ou cle USB. */
export default function Partage() {
  const [avecPortefeuille, setAvecPortefeuille] = useState(false)
  const [fichier, setFichier] = useState(null)
  const [apercu, setApercu] = useState(null)
  const [importerPortefeuille, setImporterPortefeuille] = useState(false)
  const [bilan, setBilan] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const choisir = async f => {
    setFichier(f); setApercu(null); setBilan(null); setErreur(null)
    if (!f) return
    try { setApercu(await api.systeme.apercuPartage(f)) } catch (e) { setErreur(e.message) }
  }
  const importer = async () => {
    setOccupe(true); setErreur(null)
    try { setBilan(await api.systeme.importerPartage(fichier, importerPortefeuille)); setApercu(null) }
    catch (e) { setErreur(e.message) }
    finally { setOccupe(false) }
  }
  const resume = objet => LIBELLES.filter(([cle]) => objet[cle]).map(([cle, libelle]) => `${objet[cle]} ${libelle}`).join(', ') || 'rien de nouveau'

  return (
    <div className="carte" style={{ maxWidth: 760, marginTop: 20 }}>
      <div className="section-titre">Partage avec un autre PC</div>
      <div className="carte-corps pile">
        <p className="discret" style={{ fontSize: 12.5 }}>
          Envoie vos valeurs suivies, thèses, décisions, tracés, alertes, listes, filtres et comptes saisis à la main
          dans un fichier à ouvrir sur l'autre PC (e-mail, clé USB). Les cours et comptes téléchargeables n'y sont pas :
          l'autre PC les retélécharge. À l'import, rien n'est écrasé : on ajoute seulement ce qui manque.
        </p>
        <div className="rangee">
          <a className="btn btn-primaire" href={`/api/partage/export${avecPortefeuille ? '?portefeuille=true' : ''}`}>Exporter</a>
          <label className="interrupteur">
            <input type="checkbox" checked={avecPortefeuille} onChange={e => setAvecPortefeuille(e.target.checked)} />
            Inclure le portefeuille (comptes et opérations)
          </label>
        </div>
        <div className="rangee" style={{ marginTop: 8 }}>
          <label className="btn">
            Ouvrir un fichier de partage…
            <input type="file" accept=".json,application/json" hidden onChange={e => choisir(e.target.files?.[0] ?? null)} />
          </label>
          {fichier && <span className="discret">{fichier.name}</span>}
        </div>
        {apercu && (
          <div className="pile" style={{ gap: 8 }}>
            <div>Fichier exporté le {new Date(apercu.exporte_le).toLocaleString('fr-FR')} (Bourse {apercu.application}) :
              {' '}{resume(apercu)}.</div>
            {apercu.nouvelles_valeurs.length > 0 && (
              <div className="discret">Nouvelles valeurs : {apercu.nouvelles_valeurs.join(', ')} (téléchargées ensuite).</div>
            )}
            {apercu.comptes > 0 && (
              <label className="interrupteur">
                <input type="checkbox" checked={importerPortefeuille} onChange={e => setImporterPortefeuille(e.target.checked)} />
                Importer aussi le portefeuille ({apercu.comptes} compte(s) ; un compte de même nom déjà présent est ignoré)
              </label>
            )}
            <div><button className="btn btn-primaire" disabled={occupe} onClick={importer}>{occupe ? 'Import…' : 'Importer'}</button></div>
          </div>
        )}
        {bilan && <div className="succes">Importé : {resume(bilan)}.{bilan.a_telecharger ? ' Téléchargement des nouvelles valeurs en cours.' : ''}</div>}
        {erreur && <div className="erreur">{erreur}</div>}
      </div>
    </div>
  )
}
