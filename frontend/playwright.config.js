// Tests d'interface : le backend sert l'interface construite (comme la version de bureau),
// sur une base neuve et sans acces reseau au demarrage. Lancer `npm run build` avant.
import { defineConfig } from '@playwright/test'
import os from 'node:os'
import path from 'node:path'

const PORT = 8799
const base = path.join(os.tmpdir(), `bourse-e2e-${process.pid}`, 'bourse.db')

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: { baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1300, height: 900 }, trace: 'retain-on-failure' },
  webServer: {
    command: `${process.env.PYTHON ?? 'python'} -m uvicorn backend.main:app --host 127.0.0.1 --port ${PORT}`,
    cwd: '..',
    url: `http://127.0.0.1:${PORT}/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      DB_NAME: base, DOSSIER_SAUVEGARDES: path.join(path.dirname(base), 'sauvegardes'),
      API_PREFIX: '/api', DOSSIER_FRONTEND: path.resolve('dist'),
      ACTUALISATION_AU_DEMARRAGE: 'false', NOTIFICATIONS: 'false', PYTHONUTF8: '1',
    },
  },
})
