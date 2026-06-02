import React, { useState } from 'react'
import { View } from 'react-native'
import { Screen, Title, Subtitle, Card, Button, Input, Muted, ErrorBox } from '../components/UI'
import { theme } from '../theme'
import { api } from '../api'

const WPM = 150
const words = (t) => (t || '').trim().split(/\s+/).filter(Boolean).length
const mins = (t) => Math.max(1, Math.round(words(t) / WPM))

export default function ReviewScreen({ navigate, session, setSession }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(session.script_text || '')
  const [showOriginal, setShowOriginal] = useState(false)
  const [approving, setApproving] = useState(false)
  const [error, setError] = useState('')

  const script = session.script_text || ''
  const changed = script !== (session.original_script_text || script)

  function doneEditing() {
    setSession((s) => ({ ...s, script_text: draft, duration_minutes: mins(draft) }))
    setEditing(false)
  }

  async function approve() {
    setError('')
    setApproving(true)
    try {
      const res = await api.approveScript(session.job_id, session.script_text)
      setSession((s) => ({
        ...s,
        script_text: res.script_text,
        scenes: res.scenes,
        duration_minutes: res.duration_minutes,
      }))
      navigate('Style')
    } catch (e) {
      setError(e.message || 'Failed to approve.')
      setApproving(false)
    }
  }

  return (
    <Screen>
      <Title>{session.title}</Title>
      <Subtitle>
        {words(editing ? draft : script)} words · ~{editing ? mins(draft) : session.duration_minutes} min ·{' '}
        {session.scenes?.length || 0} scenes
      </Subtitle>

      <ErrorBox>{error}</ErrorBox>

      <Card>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <Muted>Script</Muted>
          {!editing ? (
            <Button title="✎ Edit" variant="ghost" onPress={() => { setDraft(script); setEditing(true) }} style={{ marginTop: 0, minHeight: 38, paddingHorizontal: 12 }} />
          ) : (
            <Button title="✓ Done" onPress={doneEditing} style={{ marginTop: 0, minHeight: 38, paddingHorizontal: 12 }} />
          )}
        </View>
        {editing ? (
          <Input value={draft} onChangeText={setDraft} multiline />
        ) : (
          <Muted style={{ color: theme.text, lineHeight: 22 }}>{script}</Muted>
        )}
      </Card>

      {changed && !editing && (
        <>
          <Button title={showOriginal ? 'Hide Original' : '⇄ Compare Original'} variant="ghost" onPress={() => setShowOriginal((v) => !v)} />
          {showOriginal && (
            <Card style={{ borderLeftWidth: 3, borderLeftColor: theme.muted }}>
              <Muted style={{ marginBottom: 6, textTransform: 'uppercase', fontSize: 11 }}>Original AI script</Muted>
              <Muted style={{ lineHeight: 22 }}>{session.original_script_text}</Muted>
            </Card>
          )}
        </>
      )}

      <Button title={approving ? 'Preparing…' : '✓ Approve & Continue'} onPress={approve} loading={approving} disabled={editing} />
    </Screen>
  )
}
