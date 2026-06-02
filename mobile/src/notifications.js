// Firebase Cloud Messaging via expo-notifications.
// Gets the native FCM device token, registers notification categories with
// action buttons (YES/NO, Preview), and registers the token with the backend.
import { Platform } from 'react-native'
import * as Notifications from 'expo-notifications'
import * as Device from 'expo-device'
import { api } from './api'
import { getDeviceId } from './storage'

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
})

export async function setupCategories() {
  // YES/NO buttons for breaking-news; Preview button for draft-ready.
  await Notifications.setNotificationCategoryAsync('breaking_news', [
    { identifier: 'YES', buttonTitle: '✅ YES — Produce' },
    { identifier: 'NO', buttonTitle: '✖ NO — Skip' },
  ])
  await Notifications.setNotificationCategoryAsync('draft_ready', [
    { identifier: 'PREVIEW', buttonTitle: '▶ Preview' },
  ])
}

export async function registerForPush() {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Default',
      importance: Notifications.AndroidImportance.MAX,
      lightColor: '#e94560',
    })
  }
  if (!Device.isDevice) {
    return { ok: false, reason: 'Must use a physical device for push' }
  }
  const { status: existing } = await Notifications.getPermissionsAsync()
  let status = existing
  if (existing !== 'granted') {
    status = (await Notifications.requestPermissionsAsync()).status
  }
  if (status !== 'granted') {
    return { ok: false, reason: 'Notification permission not granted' }
  }
  await setupCategories()
  try {
    // Native FCM token (requires google-services.json in the build).
    const tokenResp = await Notifications.getDevicePushTokenAsync()
    const token = tokenResp?.data
    const deviceId = await getDeviceId()
    if (token) {
      await api.registerDevice(token, deviceId)
      return { ok: true, token, deviceId }
    }
    return { ok: false, reason: 'No FCM token returned' }
  } catch (e) {
    return { ok: false, reason: e.message || 'Token registration failed' }
  }
}
