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

export const api = {
  valeurs: {
    list:       ()          => request('/valeurs'),
    synthese:   ()          => request('/valeurs/synthese'),
    recherche:  (q)         => request(`/valeurs/recherche${parametres({ q })}`),
    get:        (id)        => request(`/valeurs/${id}`),
    analyse:    (id, opts)  => request(`/valeurs/${id}/analyse${parametres(opts)}`),
    create:     (data)      => request('/valeurs', { method: 'POST', ...corps(data) }),
    update:     (id, data)  => request(`/valeurs/${id}`, { method: 'PATCH', ...corps(data) }),
    remove:     (id)        => request(`/valeurs/${id}`, { method: 'DELETE' }),
    actualiser: (id)        => request(`/valeurs/${id}/actualiser`, { method: 'POST' }),
    actualiserTout: ()      => request('/valeurs/actualiser', { method: 'POST' }),
  },

  fondamentaux: {
    list:   (id)              => request(`/valeurs/${id}/fondamentaux`),
    ecrire: (id, annee, data) => request(`/valeurs/${id}/fondamentaux/${annee}`, { method: 'PUT', ...corps(data) }),
    remove: (id, annee)       => request(`/valeurs/${id}/fondamentaux/${annee}`, { method: 'DELETE' }),
  },

  imports: {
    cours:        (id, f) => request(`/valeurs/${id}/import/cours`, fichier(f)),
    fondamentaux: (id, f) => request(`/valeurs/${id}/import/fondamentaux`, fichier(f)),
  },
}
