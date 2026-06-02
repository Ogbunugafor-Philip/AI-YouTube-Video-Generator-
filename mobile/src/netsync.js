// Connectivity-aware draft sync. When the device regains internet, any
// offline drafts are pushed to the backend (script generation) and marked
// synced so they appear in the dashboard / history.
import NetInfo from '@react-native-community/netinfo'
import { api } from './api'
import { pendingDrafts, markSynced } from './storage'

export function subscribeConnectivity(onChange) {
  return NetInfo.addEventListener((state) => {
    onChange(!!(state.isConnected && state.isInternetReachable !== false))
  })
}

export async function isOnline() {
  const s = await NetInfo.fetch()
  return !!(s.isConnected && s.isInternetReachable !== false)
}

// Sync all pending drafts. Returns {synced, failed}. A draft "syncs" by being
// submitted to the backend as a script-generation job.
export async function syncPendingDrafts(onProgress) {
  if (!(await isOnline())) return { synced: 0, failed: 0, offline: true }
  const drafts = await pendingDrafts()
  let synced = 0
  let failed = 0
  for (const d of drafts) {
    try {
      const payload = {
        mode: d.mode || 'topic',
        duration_minutes: d.duration || 3,
        topic: d.mode === 'topic' ? d.topic : null,
        content: d.mode === 'writeup' ? d.content : null,
      }
      // Only sync drafts that actually have content.
      const hasContent = d.mode === 'writeup' ? !!d.content?.trim() : !!d.topic?.trim()
      if (!hasContent) continue
      const res = await api.generateScript(payload)
      await markSynced(d.id)
      synced += 1
      if (onProgress) onProgress({ draft: d, job: res })
    } catch (e) {
      failed += 1
    }
  }
  return { synced, failed }
}
