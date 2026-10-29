// @ts-check
const BASE = '/api'

function messageErreur(data) {
  if (!data) return null
  const { detail } = data
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(e => e.msg).join(' · ')
  return null
}

async function request(path, options = {}) {
  let reponse
  try {
    reponse = await fetch(BASE + path, {
      headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    // Rien au bout du fil : application arretee, ou mauvaise adresse.
    throw new Error("Serveur injoignable — l'application tourne-t-elle ?")
  }

  if (reponse.status === 204) return null

  const data = await reponse.json().catch(() => null)
  if (!reponse.ok) {
    // Sans detail JSON, le code HTTP est la seule piste : une page d'erreur
    // du serveur web (502, 504) ne dit rien d'autre.
    throw new Error(messageErreur(data) || `Erreur serveur (${reponse.status}).`)
  }
  return data
}

const corps = (data) => ({ body: JSON.stringify(data) })

/** Transforme un objet en chaine de requete. */
function parametres(filtres) {
  const params = new URLSearchParams()
  Object.entries(filtres).forEach(([cle, valeur]) => {
    if (valeur === undefined || valeur === null || valeur === '') return
    params.append(cle, valeur)
  })
  const texte = params.toString()
  return texte ? `?${texte}` : ''
}

function fichier(f) {
  const donnees = new FormData()
  donnees.append('fichier', f)
  return { method: 'POST', body: donnees }
}

/** Reponse texte lue morceau par morceau (assistant) : `surMorceau` recoit le texte deja recu. */
export async function flux(path, donnees, surMorceau) {
  const reponse = await fetch(BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(donnees) })
  if (!reponse.ok) {
    const data = await reponse.json().catch(() => null)
    throw new Error(messageErreur(data) || `Erreur serveur (${reponse.status}).`)
  }
  const lecteur = reponse.body.getReader()
  const decodeur = new TextDecoder()
  let texte = ''
  for (;;) {
    const { done, value } = await lecteur.read()
    if (done) return texte
    texte += decodeur.decode(value, { stream: true })
    surMorceau(texte)
  }
}

export const api = {
  valeurs: {
    list:       ()          => request('/valeurs'),
    synthese:   ()          => request('/valeurs/synthese'),
    catalogue:  ()          => request('/valeurs/catalogue'),
    recherche:  (q)         => request(`/valeurs/recherche${parametres({ q })}`),
    get:        (id)        => request(`/valeurs/${id}`),
    analyse:    (id, opts)  => request(`/valeurs/${id}/analyse${parametres(opts)}`),
    create:     (data)      => request('/valeurs', { method: 'POST', ...corps(data) }),
    supprimer:  (ids, confirmer = false) => request('/valeurs/supprimer', { method: 'POST', ...corps({ ids, confirmer }) }),
    update:     (id, data)  => request(`/valeurs/${id}`, { method: 'PATCH', ...corps(data) }),
    remove:     (id)        => request(`/valeurs/${id}`, { method: 'DELETE' }),
    actualiser: (id)        => request(`/valeurs/${id}/actualiser`, { method: 'POST' }),
    actualiserTout: (mode = 'cours') => request(`/valeurs/actualiser?mode=${mode}`, { method: 'POST' }),
    actualisation:  ()      => request('/valeurs/actualisation'),
    technique:      (id, opts) => request(`/valeurs/${id}/technique${parametres(opts)}`),
    annotations:    (id)     => request(`/valeurs/${id}/annotations`),
    annoter:        (id, data) => request(`/valeurs/${id}/annotations`, { method: 'POST', ...corps(data) }),
    effacerAnnotation: (id, a) => request(`/valeurs/${id}/annotations/${a}`, { method: 'DELETE' }),
    valorisation:   (id, h)  => request(`/valeurs/${id}/valorisation${parametres(h)}`),
    consensus:      (id)     => request(`/valeurs/${id}/consensus`),
    secteur:        (id)     => request(`/valeurs/${id}/secteur`),
  },

  fondamentaux: {
    list:   (id)              => request(`/valeurs/${id}/fondamentaux`),
    ecrire: (id, annee, data) => request(`/valeurs/${id}/fondamentaux/${annee}`, { method: 'PUT', ...corps(data) }),
    remove: (id, annee)       => request(`/valeurs/${id}/fondamentaux/${annee}`, { method: 'DELETE' }),
  },

  imports: {
    cours:        (id, f) => request(`/valeurs/${id}/import/cours`, fichier(f)),
    fondamentaux: (id, f) => request(`/valeurs/${id}/import/fondamentaux`, fichier(f)),
    pdf:          (id, f) => request(`/valeurs/${id}/import/pdf`, fichier(f)),
    lot:          (id, annees, source = 'pdf') => request(`/valeurs/${id}/import/lot`, { method: 'POST', ...corps({ annees, source }) }),
    coller:       (id, texte) => request(`/valeurs/${id}/import/fondamentaux/texte`, { method: 'POST', ...corps({ texte }) }),
  },

  journal: {
    these:          (id)          => request(`/valeurs/${id}/journal/these`),
    ecrireThese:    (id, data)    => request(`/valeurs/${id}/journal/these`, { method: 'PUT', ...corps(data) }),
    decisions:      (id)          => request(`/valeurs/${id}/journal/decisions`),
    ajouterDecision:(id, data)    => request(`/valeurs/${id}/journal/decisions`, { method: 'POST', ...corps(data) }),
    modifierDecision:(id, d, data) => request(`/valeurs/${id}/journal/decisions/${d}`, { method: 'PUT', ...corps(data) }),
    supprimerDecision:(id, d)     => request(`/valeurs/${id}/journal/decisions/${d}`, { method: 'DELETE' }),
    pieces:         (id)          => request(`/valeurs/${id}/journal/pieces`),
    ajouterPiece:   (id, f)       => request(`/valeurs/${id}/journal/pieces`, fichier(f)),
    supprimerPiece: (id, p)       => request(`/valeurs/${id}/journal/pieces/${p}`, { method: 'DELETE' }),
    lienPiece:      (id, p)       => `${BASE}/valeurs/${id}/journal/pieces/${p}`,
  },

  portefeuille: {
    synthese:      (compteId)     => request(`/portefeuille${parametres({ compte_id: compteId })}`),
    comptes:       ()             => request('/portefeuille/comptes'),
    creerCompte:   (data)         => request('/portefeuille/comptes', { method: 'POST', ...corps(data) }),
    modifierCompte:(id, data)     => request(`/portefeuille/comptes/${id}`, { method: 'PUT', ...corps(data) }),
    supprimerCompte:(id)          => request(`/portefeuille/comptes/${id}`, { method: 'DELETE' }),
    transactions:  (compteId)     => request(`/portefeuille/transactions${parametres({ compte_id: compteId })}`),
    creerTransaction:(data)       => request('/portefeuille/transactions', { method: 'POST', ...corps(data) }),
    supprimerTransaction:(id)     => request(`/portefeuille/transactions/${id}`, { method: 'DELETE' }),
    frais:         (opts)         => request(`/portefeuille/frais${parametres(opts)}`),
    lireReleve:    (compteId, f)  => request(`/portefeuille/comptes/${compteId}/releve`, fichier(f)),
    validerReleve: (compteId, lignes) => request(`/portefeuille/comptes/${compteId}/releve/valider`, { method: 'POST', ...corps({ lignes }) }),
  },

  alertes: {
    list:           (valeurId) => request(`/alertes${parametres({ valeur_id: valeurId })}`),
    creer:          (data)     => request('/alertes', { method: 'POST', ...corps(data) }),
    modifier:       (id, data) => request(`/alertes/${id}`, { method: 'PUT', ...corps(data) }),
    supprimer:      (id)       => request(`/alertes/${id}`, { method: 'DELETE' }),
    declenchements: ()         => request('/alertes/declenchements'),
    marquerLues:    ()         => request('/alertes/lues', { method: 'POST' }),
    essai:          ()         => request('/alertes/essai', { method: 'POST' }),
  },

  univers: {
    list:       ()                 => request('/univers'),
    composition:(cle)              => request(`/univers/${cle}`),
    importer:   (cle, symboles, liste) => request(`/univers/${cle}/importer`, { method: 'POST', ...corps({ symboles, liste }) }),
  },
  listes: {
    list:      ()           => request('/listes'),
    creer:     (nom)        => request('/listes', { method: 'POST', ...corps({ nom }) }),
    supprimer: (id)         => request(`/listes/${id}`, { method: 'DELETE' }),
    ajouter:   (id, ids)    => request(`/listes/${id}/valeurs`, { method: 'POST', ...corps({ valeur_ids: ids }) }),
    retirer:   (id, vid)    => request(`/listes/${id}/valeurs/${vid}`, { method: 'DELETE' }),
  },
  screener:  (listeId) => request(`/screener${parametres({ liste_id: listeId })}`),
  filtres: {
    list:      ()              => request('/filtres'),
    enregistrer:(nom, criteres) => request('/filtres', { method: 'PUT', ...corps({ nom, criteres }) }),
    supprimer: (id)            => request(`/filtres/${id}`, { method: 'DELETE' }),
  },
  comparer:  (opts) => request(`/comparer${parametres(opts)}`),
  backtest:  (valeurId, opts) => request(`/backtest${valeurId ? `/${valeurId}` : ''}${parametres(opts)}`),

  calendrier:  (opts) => request(`/calendrier${parametres(opts || {})}`),
  actualites:  (id)   => request(`/valeurs/${id}/actualites`),
  resume:      ()     => request('/resume'),

  champs: () => request('/champs'),

  assistant: {
    etat:        ()          => request('/assistant'),
    analyses:    id          => request(`/valeurs/${id}/assistant`),
    supprimer:   (id, a)     => request(`/valeurs/${id}/assistant/${a}`, { method: 'DELETE' }),
    lireRapport: (id, f)     => request(`/valeurs/${id}/assistant/rapport`, fichier(f)),
    relirePiece: (id, piece) => request(`/valeurs/${id}/assistant/rapport/${piece}`, { method: 'POST' }),
    travail:     t           => request(`/assistant/travaux/${t}`),
    actualites:  id          => request(`/valeurs/${id}/assistant/actualites`, { method: 'POST' }),
  },
  systeme: {
    aPropos: () => request('/a-propos'),
    sauvegardes: () => request('/sauvegardes'),
    sauvegarder: () => request('/sauvegardes', { method: 'POST' }),
    restaurer: chemin => request('/sauvegardes/restaurer', { method: 'POST', ...corps({ chemin }) }),
    apercuPartage: f => request('/partage/apercu', fichier(f)),
    importerPartage: (f, portefeuille) => request(`/partage/importer${parametres({ portefeuille })}`, fichier(f)),
  },
  reglages: {
    list:   ()            => request('/reglages'),
    ecrire: (cle, valeur) => request(`/reglages/${cle}`, { method: 'PUT', ...corps({ valeur }) }),
  },
}
