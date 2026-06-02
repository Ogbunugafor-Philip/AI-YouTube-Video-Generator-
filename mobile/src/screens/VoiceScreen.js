import React, { useEffect, useState } from 'react'
import { View, Linking } from 'react-native'
import { Screen, Title, Subtitle, Card, Button, Muted, ErrorBox } from '../components/UI'
import { theme } from '../theme'
import { api } from '../api'

export default function VoiceScreen({ navigate, session, setSession }) {
  const [voices, setVoices] = useState([])
  const [selected, setSelected] = useState(session.voice || '')
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .getVoiceOptions()
      .then((r) => {
        setVoices(r.voices || [])
        setSelected(session.voice || r.default || r.voices?.[0]?.id || '')
      })
      .catch((e) => setError(e.message))
  }, [])

  function preview(id) {
    // Plays in the device browser (no extra native audio dependency).
    Linking.openURL(api.voicePreviewUrl(id)).catch(() => {})
  }

  function next() {
    setSession((s) => ({ ...s, voice: selected }))
    navigate('SceneEditor')
  }

  return (
    <Screen>
      <Title>Choose a voice</Title>
      <Subtitle>Step 2 of 3 · Tap Preview to hear a sample.</Subtitle>
      <ErrorBox>{error}</ErrorBox>
      {voices.map((v) => (
        <Card
          key={v.id}
          onPress={() => setSelected(v.id)}
          style={selected === v.id ? { borderColor: theme.accent, borderWidth: 2, backgroundColor: 'rgba(233,69,96,0.08)' } : null}
        >
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <View style={{ flex: 1, paddingRight: 10 }}>
              <Muted style={{ color: theme.text, fontSize: 17, fontWeight: '800' }}>
                {selected === v.id ? '◉' : '○'}  {v.name}
              </Muted>
              <Muted style={{ marginTop: 4 }}>{v.description}</Muted>
            </View>
            <Button title="▶ Preview" variant="ghost" onPress={() => preview(v.id)} style={{ marginTop: 0, minHeight: 40, paddingHorizontal: 12 }} />
          </View>
        </Card>
      ))}
      <Button title="Continue →" onPress={next} disabled={!selected} />
    </Screen>
  )
}
