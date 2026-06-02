// Local persistence via AsyncStorage: offline drafts + a stable device id.
import AsyncStorage from '@react-native-async-storage/async-storage'

const DRAFTS_KEY = 'vidgen_drafts'
const DEVICE_ID_KEY = 'vidgen_device_id'

function uid() {
  return (
    Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
  )
}

export async function getDeviceId() {
  let id = await AsyncStorage.getItem(DEVICE_ID_KEY)
  if (!id) {
    id = 'dev_' + uid()
    await AsyncStorage.setItem(DEVICE_ID_KEY, id)
  }
  return id
}

export async function getDrafts() {
  try {
    const raw = await AsyncStorage.getItem(DRAFTS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch (e) {
    return []
  }
}

export async function saveDraft(draft) {
  const drafts = await getDrafts()
  const now = new Date().toISOString()
  if (draft.id) {
    const idx = drafts.findIndex((d) => d.id === draft.id)
    if (idx >= 0) drafts[idx] = { ...drafts[idx], ...draft, updatedAt: now }
  } else {
    drafts.push({
      id: uid(),
      mode: draft.mode || 'topic',
      topic: draft.topic || '',
      content: draft.content || '',
      duration: draft.duration || 3,
      synced: false,
      createdAt: now,
      updatedAt: now,
    })
  }
  await AsyncStorage.setItem(DRAFTS_KEY, JSON.stringify(drafts))
  return drafts
}

export async function deleteDraft(id) {
  const drafts = (await getDrafts()).filter((d) => d.id !== id)
  await AsyncStorage.setItem(DRAFTS_KEY, JSON.stringify(drafts))
  return drafts
}

export async function markSynced(id) {
  const drafts = await getDrafts()
  const idx = drafts.findIndex((d) => d.id === id)
  if (idx >= 0) {
    drafts[idx].synced = true
    drafts[idx].syncedAt = new Date().toISOString()
    await AsyncStorage.setItem(DRAFTS_KEY, JSON.stringify(drafts))
  }
  return drafts
}

export async function pendingDrafts() {
  return (await getDrafts()).filter((d) => !d.synced)
}
