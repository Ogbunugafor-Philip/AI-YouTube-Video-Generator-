import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Linking,
  Platform,
  StatusBar,
} from 'react-native'
import { StatusBar as ExpoStatusBar } from 'expo-status-bar'
import * as Notifications from 'expo-notifications'

import { theme } from './src/theme'
import { api } from './src/api'
import { registerForPush } from './src/notifications'
import { subscribeConnectivity, syncPendingDrafts } from './src/netsync'

import HomeScreen from './src/screens/HomeScreen'
import ReviewScreen from './src/screens/ReviewScreen'
import StyleScreen from './src/screens/StyleScreen'
import VoiceScreen from './src/screens/VoiceScreen'
import SceneEditorScreen from './src/screens/SceneEditorScreen'
import ProgressScreen from './src/screens/ProgressScreen'
import ResultScreen from './src/screens/ResultScreen'
import HistoryScreen from './src/screens/HistoryScreen'
import DraftsScreen from './src/screens/DraftsScreen'

const SCREENS = {
  Home: HomeScreen,
  Review: ReviewScreen,
  Style: StyleScreen,
  Voice: VoiceScreen,
  SceneEditor: SceneEditorScreen,
  Progress: ProgressScreen,
  Result: ResultScreen,
  History: HistoryScreen,
  Drafts: DraftsScreen,
}

const TITLES = {
  Home: 'VidGen Studio',
  Review: 'Review Script',
  Style: 'Video Style',
  Voice: 'Narration Voice',
  SceneEditor: 'Scene Editor',
  Progress: 'Producing',
  Result: 'Your Video',
  History: 'Video History',
  Drafts: 'Drafts',
}

export default function App() {
  const [stack, setStack] = useState([{ screen: 'Home', params: {} }])
  const [session, setSession] = useState({}) // in-progress production flow
  const [online, setOnline] = useState(true)
  const [syncMsg, setSyncMsg] = useState('')
  const respListener = useRef(null)

  const top = stack[stack.length - 1]

  const navigate = useCallback((screen, params = {}) => {
    setStack((st) => [...st, { screen, params }])
  }, [])
  const goBack = useCallback(() => {
    setStack((st) => (st.length > 1 ? st.slice(0, -1) : st))
  }, [])
  const resetTo = useCallback((screen, params = {}) => {
    setStack([{ screen, params }])
  }, [])

  // --- Push notifications: register token + handle action taps ---
  useEffect(() => {
    registerForPush().catch(() => {})

    respListener.current = Notifications.addNotificationResponseReceivedListener((resp) => {
      const data = resp?.notification?.request?.content?.data || {}
      const action = resp.actionIdentifier // 'YES' | 'NO' | 'PREVIEW' | default
      if (data.type === 'breaking_news') {
        if (action === 'NO') return // silently skip
        // YES (or tapping the notification) triggers production on the backend.
        if (data.story_id) {
          api.triggerStory(data.story_id).catch(() => {})
          setSyncMsg('Breaking-news production started ✓')
        }
      } else if (data.type === 'draft_ready') {
        if (data.draft_url) Linking.openURL(data.draft_url).catch(() => {})
      }
    })
    return () => {
      if (respListener.current) respListener.current.remove()
    }
  }, [])

  // --- Connectivity: auto-sync pending drafts when back online ---
  useEffect(() => {
    const unsub = subscribeConnectivity(async (isOnline) => {
      setOnline(isOnline)
      if (isOnline) {
        const r = await syncPendingDrafts()
        if (r.synced > 0) setSyncMsg(`Synced ${r.synced} draft(s) ✓`)
      }
    })
    return () => unsub && unsub()
  }, [])

  useEffect(() => {
    if (!syncMsg) return
    const t = setTimeout(() => setSyncMsg(''), 4000)
    return () => clearTimeout(t)
  }, [syncMsg])

  const ScreenComp = SCREENS[top.screen] || HomeScreen

  return (
    <View style={styles.app}>
      <ExpoStatusBar style="light" />
      <View style={{ height: Platform.OS === 'android' ? StatusBar.currentHeight : 0 }} />
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          {stack.length > 1 ? (
            <TouchableOpacity onPress={goBack} style={styles.backBtn} hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}>
              <Text style={styles.backText}>‹</Text>
            </TouchableOpacity>
          ) : (
            <Text style={styles.brandMark}>▶</Text>
          )}
          <Text style={styles.headerTitle}>{TITLES[top.screen] || 'VidGen'}</Text>
        </View>
        <View style={styles.headerRight}>
          <TouchableOpacity onPress={() => resetTo('Home')}>
            <Text style={styles.navItem}>Home</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigate('Drafts')}>
            <Text style={styles.navItem}>Drafts</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigate('History')}>
            <Text style={styles.navItem}>History</Text>
          </TouchableOpacity>
        </View>
      </View>

      {!online && (
        <View style={styles.offlineBar}>
          <Text style={styles.offlineText}>Offline — drafts will sync when reconnected</Text>
        </View>
      )}
      {syncMsg ? (
        <View style={styles.syncBar}>
          <Text style={styles.syncText}>{syncMsg}</Text>
        </View>
      ) : null}

      <View style={{ flex: 1 }}>
        <ScreenComp
          navigate={navigate}
          goBack={goBack}
          resetTo={resetTo}
          session={session}
          setSession={setSession}
          params={top.params}
          online={online}
        />
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  app: { flex: 1, backgroundColor: theme.navy },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: 'rgba(0,0,0,0.25)',
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  headerLeft: { flexDirection: 'row', alignItems: 'center' },
  backBtn: { marginRight: 8 },
  backText: { color: theme.text, fontSize: 30, lineHeight: 30, fontWeight: '700' },
  brandMark: { color: theme.accent, fontSize: 18, marginRight: 8 },
  headerTitle: { color: theme.text, fontSize: 18, fontWeight: '800' },
  headerRight: { flexDirection: 'row', alignItems: 'center' },
  navItem: { color: theme.muted, fontWeight: '700', marginLeft: 14, fontSize: 13 },
  offlineBar: { backgroundColor: 'rgba(241,196,15,0.15)', padding: 8, alignItems: 'center' },
  offlineText: { color: theme.warn, fontSize: 12, fontWeight: '600' },
  syncBar: { backgroundColor: 'rgba(46,204,113,0.15)', padding: 8, alignItems: 'center' },
  syncText: { color: theme.ok, fontSize: 12, fontWeight: '700' },
})
