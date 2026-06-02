import React, { useEffect, useRef, useState } from 'react'
import { View, StyleSheet } from 'react-native'
import { Screen, Title, Subtitle, Card, Muted, ErrorBox } from '../components/UI'
import { theme } from '../theme'
import { api } from '../api'

export default function ProgressScreen({ navigate, session, setSession }) {
  const [state, setState] = useState({ percentage: 0, step: 'Starting…', scenes_total: session.scenes?.length || 0, scenes_completed: 0 })
  const [error, setError] = useState('')
  const timer = useRef(null)

  useEffect(() => {
    async function poll() {
      try {
        const st = await api.status(session.job_id)
        setState(st)
        if (st.status === 'complete') {
          clearInterval(timer.current)
          setSession((s) => ({ ...s, video_path: st.video_path, thumbnail_url: st.thumbnail_url }))
          navigate('Result')
        } else if (st.status === 'error') {
          clearInterval(timer.current)
          setError(st.error || st.step || 'Production failed.')
        }
      } catch (e) {
        // keep polling; transient
      }
    }
    poll()
    timer.current = setInterval(poll, 2500)
    return () => clearInterval(timer.current)
  }, [])

  const total = state.scenes_total || 0
  const done = state.scenes_completed || 0

  return (
    <Screen>
      <Title>Producing your video</Title>
      <Subtitle>{session.title}</Subtitle>
      <ErrorBox>{error}</ErrorBox>

      <Card style={{ alignItems: 'center', paddingVertical: 28 }}>
        <Muted style={{ color: theme.accent, fontSize: 44, fontWeight: '900' }}>{Math.round(state.percentage)}%</Muted>
        <Muted style={{ color: theme.text, fontSize: 16, fontWeight: '700', marginVertical: 6, textAlign: 'center' }}>
          {state.step || 'Working…'}
        </Muted>
        <View style={st.barTrack}>
          <View style={[st.barFill, { width: `${Math.max(2, state.percentage)}%` }]} />
        </View>
        {total > 0 && (
          <Muted style={{ marginTop: 12 }}>{done} / {total} scenes rendered</Muted>
        )}
      </Card>
      <Muted style={{ textAlign: 'center' }}>Keep this screen open — production runs on the cloud.</Muted>
    </Screen>
  )
}

const st = StyleSheet.create({
  barTrack: { width: '100%', height: 18, borderRadius: 999, backgroundColor: 'rgba(0,0,0,0.35)', overflow: 'hidden', marginTop: 16 },
  barFill: { height: '100%', backgroundColor: theme.accent, borderRadius: 999 },
})
