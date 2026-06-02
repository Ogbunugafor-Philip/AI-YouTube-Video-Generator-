// Backend API client. All production runs on the existing FastAPI backend;
// this app is just the mobile interface. Base URL comes from app.json `extra`
// (not hardcoded in source).
import Constants from 'expo-constants'

export const BASE_URL =
  Constants.expoConfig?.extra?.apiBaseUrl ||
  Constants.manifest?.extra?.apiBaseUrl ||
  'https://vidgen.store'

async function req(path, { method = 'GET', body } = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch (e) {
      /* ignore */
    }
    throw new Error(detail)
  }
  // Some endpoints return no JSON body.
  const text = await res.text()
  return text ? JSON.parse(text) : {}
}

export const api = {
  // --- production pipeline (existing routes) ---
  generateScript: (payload) => req('/api/script/generate', { method: 'POST', body: payload }),
  approveScript: (jobId, scriptText) =>
    req('/api/script/approve', { method: 'POST', body: { job_id: jobId, script_text: scriptText ?? null } }),
  getStyleOptions: () => req('/api/style/options'),
  getVoiceOptions: () => req('/api/voice/options'),
  voicePreviewUrl: (voiceId) => `${BASE_URL}/api/voice/preview/${voiceId}`,
  produce: (payload) => req('/api/video/produce', { method: 'POST', body: payload }),
  status: (jobId) => req(`/api/video/status/${jobId}`),
  downloadUrl: (jobId) => `${BASE_URL}/api/video/download/${jobId}`,
  mediaUrl: (path) => (path?.startsWith('http') ? path : `${BASE_URL}${path}`),
  regenerateThumbnail: (jobId, title) =>
    req('/api/thumbnail/regenerate', { method: 'POST', body: { job_id: jobId, title } }),
  uploadToYoutube: (jobId) => req('/api/video/upload', { method: 'POST', body: { job_id: jobId } }),
  publish: (payload) => req('/api/video/publish', { method: 'POST', body: payload }),
  // --- history ---
  getHistory: () => req('/api/history'),
  getHistoryDetail: (jobId) => req(`/api/history/${jobId}`),
  // --- breaking news ---
  triggerStory: (storyId) => req(`/api/news/trigger/${storyId}`, { method: 'POST' }),
  // --- FCM ---
  registerDevice: (deviceToken, deviceId) =>
    req('/api/fcm/register-device', {
      method: 'POST',
      body: { device_token: deviceToken, device_id: deviceId, platform: 'android' },
    }),
}
