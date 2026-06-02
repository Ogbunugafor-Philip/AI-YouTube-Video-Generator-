import React, { useState } from 'react'
import { View } from 'react-native'
import { Screen, Title, Subtitle, Card, Button, Input, Pill, ErrorBox, NoticeBox, Muted } from '../components/UI'
import { api } from '../api'
import { saveDraft } from '../storage'

const DURATIONS = [3, 4, 5]

export default function HomeScreen({ navigate, setSession, online }) {
  const [mode, setMode] = useState('topic')
  const [topic, setTopic] = useState('')
  const [content, setContent] = useState('')
  const [duration, setDuration] = useState(3)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const valid = mode === 'topic' ? topic.trim() : content.trim()

  async function handleGenerate() {
    setError('')
    if (!valid) {
      setError(mode === 'topic' ? 'Enter a topic.' : 'Paste your write-up.')
      return
    }
    if (!online) {
      await handleSaveDraft()
      return
    }
    setLoading(true)
    try {
      const data = await api.generateScript({
        mode,
        duration_minutes: duration,
        topic: mode === 'topic' ? topic : null,
        content: mode === 'writeup' ? content : null,
      })
      setSession({
        job_id: data.job_id,
        title: data.title,
        script_text: data.script_text,
        original_script_text: data.script_text,
        scenes: data.scenes,
        duration_minutes: duration,
        mode,
      })
      navigate('Review')
    } catch (e) {
      setError(e.message || 'Failed to generate script.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveDraft() {
    if (!valid) {
      setError('Nothing to save yet.')
      return
    }
    await saveDraft({ mode, topic, content, duration })
    setNotice(online ? 'Saved to drafts.' : 'Saved offline — will sync when reconnected.')
    setTopic('')
    setContent('')
  }

  return (
    <Screen>
      <Title>Create a video</Title>
      <Subtitle>Pick a mode, describe your idea, and produce on the cloud.</Subtitle>

      <ErrorBox>{error}</ErrorBox>
      <NoticeBox>{notice}</NoticeBox>

      <View style={{ flexDirection: 'row', marginBottom: 8 }}>
        <Pill label="💡 Topic" active={mode === 'topic'} onPress={() => setMode('topic')} />
        <Pill label="📝 Write-Up" active={mode === 'writeup'} onPress={() => setMode('writeup')} />
      </View>

      <Card>
        {mode === 'topic' ? (
          <>
            <Muted>What should the video be about?</Muted>
            <Input
              value={topic}
              onChangeText={setTopic}
              placeholder="e.g. How AI is changing Nigerian banking"
              style={{ marginTop: 8 }}
            />
            <Muted style={{ marginTop: 16, marginBottom: 8 }}>Duration</Muted>
            <View style={{ flexDirection: 'row' }}>
              {DURATIONS.map((d) => (
                <Pill key={d} label={`${d} min`} active={duration === d} onPress={() => setDuration(d)} />
              ))}
            </View>
          </>
        ) : (
          <>
            <Muted>Paste your script — your words are used exactly.</Muted>
            <Input
              value={content}
              onChangeText={setContent}
              placeholder="Paste your full narration here…"
              multiline
              style={{ marginTop: 8 }}
            />
          </>
        )}
      </Card>

      <Button
        title={online ? 'Generate Script' : 'Save Draft (offline)'}
        onPress={handleGenerate}
        loading={loading}
      />
      <Button title="Save as Draft" variant="ghost" onPress={handleSaveDraft} />
      <Button title="📁 My Drafts" variant="ghost" onPress={() => navigate('Drafts')} />
    </Screen>
  )
}
