import React, { useState } from 'react'
import { Screen, Title, Subtitle, Card, Button, Input, Muted, ErrorBox } from '../components/UI'
import { theme } from '../theme'
import { api } from '../api'

export default function SceneEditorScreen({ navigate, session }) {
  const [scenes, setScenes] = useState((session.scenes || []).map((s) => ({ ...s })))
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')

  function edit(idx, value) {
    setScenes((prev) => prev.map((s, i) => (i === idx ? { ...s, visual_description: value } : s)))
  }

  async function proceed() {
    setError('')
    setStarting(true)
    try {
      await api.produce({
        job_id: session.job_id,
        scenes,
        voice: session.voice || null,
        video_style: session.video_style || null,
      })
      navigate('Progress')
    } catch (e) {
      setError(e.message || 'Failed to start generation.')
      setStarting(false)
    }
  }

  return (
    <Screen>
      <Title>Scene editor</Title>
      <Subtitle>Step 3 of 3 · {scenes.length} scenes. Editing is optional.</Subtitle>
      <ErrorBox>{error}</ErrorBox>
      {scenes.map((s, idx) => (
        <Card key={s.scene_number ?? idx} style={{ borderLeftWidth: 3, borderLeftColor: theme.accent }}>
          <Muted style={{ color: theme.accent, fontWeight: '800', fontSize: 12 }}>SCENE {s.scene_number ?? idx + 1}</Muted>
          <Muted style={{ color: theme.text, marginVertical: 6 }}>{s.narration_text}</Muted>
          <Muted style={{ fontSize: 12, marginBottom: 4 }}>🎬 Visual description</Muted>
          <Input value={s.visual_description} onChangeText={(t) => edit(idx, t)} multiline style={{ minHeight: 70 }} />
        </Card>
      ))}
      <Button title={starting ? 'Starting…' : '▶ Proceed to Generation'} onPress={proceed} loading={starting} />
    </Screen>
  )
}
