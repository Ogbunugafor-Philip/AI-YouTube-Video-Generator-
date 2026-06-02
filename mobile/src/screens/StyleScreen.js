import React, { useEffect, useState } from 'react'
import { Screen, Title, Subtitle, Card, Button, Muted, ErrorBox } from '../components/UI'
import { theme } from '../theme'
import { api } from '../api'

const ICONS = { cinematic: '🎬', minimalist: '⬜', corporate: '🏢', vibrant: '🌈' }

export default function StyleScreen({ navigate, session, setSession }) {
  const [styles, setStyles] = useState([])
  const [selected, setSelected] = useState(session.video_style || 'cinematic')
  const [error, setError] = useState('')

  useEffect(() => {
    api.getStyleOptions().then((r) => setStyles(r.styles || [])).catch((e) => setError(e.message))
  }, [])

  function next() {
    setSession((s) => ({ ...s, video_style: selected }))
    navigate('Voice')
  }

  return (
    <Screen>
      <Title>Choose a style</Title>
      <Subtitle>Step 1 of 3 · Applied to every generated scene.</Subtitle>
      <ErrorBox>{error}</ErrorBox>
      {styles.map((st) => (
        <Card
          key={st.id}
          onPress={() => setSelected(st.id)}
          style={selected === st.id ? { borderColor: theme.accent, borderWidth: 2, backgroundColor: 'rgba(233,69,96,0.08)' } : null}
        >
          <Muted style={{ color: theme.text, fontSize: 18, fontWeight: '800' }}>
            {ICONS[st.id] || '🎨'}  {st.name}
          </Muted>
          <Muted style={{ marginTop: 4 }}>{st.description}</Muted>
        </Card>
      ))}
      <Button title="Continue →" onPress={next} disabled={!selected} />
    </Screen>
  )
}
