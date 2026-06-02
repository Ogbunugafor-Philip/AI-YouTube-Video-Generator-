import React, { useEffect, useState, useCallback } from 'react'
import { View } from 'react-native'
import { Screen, Title, Subtitle, Card, Button, Input, Pill, Muted, ErrorBox, NoticeBox } from '../components/UI'
import { theme } from '../theme'
import { getDrafts, saveDraft, deleteDraft } from '../storage'
import { syncPendingDrafts, isOnline } from '../netsync'

export default function DraftsScreen({ online }) {
  const [drafts, setDrafts] = useState([])
  const [mode, setMode] = useState('topic')
  const [topic, setTopic] = useState('')
  const [content, setContent] = useState('')
  const [duration, setDuration] = useState(3)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [syncing, setSyncing] = useState(false)

  const refresh = useCallback(async () => setDrafts(await getDrafts()), [])
  useEffect(() => { refresh() }, [refresh])

  async function add() {
    const valid = mode === 'topic' ? topic.trim() : content.trim()
    if (!valid) { setError('Nothing to save.'); return }
    setError('')
    await saveDraft({ mode, topic, content, duration })
    setTopic(''); setContent('')
    setNotice('Draft saved locally.')
    refresh()
  }

  async function remove(id) { await deleteDraft(id); refresh() }

  async function sync() {
    setError(''); setNotice(''); setSyncing(true)
    try {
      if (!(await isOnline())) { setError('No internet — drafts will sync automatically when reconnected.'); return }
      const r = await syncPendingDrafts()
      setNotice(`Synced ${r.synced} draft(s)${r.failed ? `, ${r.failed} failed` : ''}.`)
      refresh()
    } finally { setSyncing(false) }
  }

  const pending = drafts.filter((d) => !d.synced).length

  return (
    <Screen>
      <Title>Drafts</Title>
      <Subtitle>
        Write offline — they sync automatically when you're back online.
        {pending > 0 ? `  (${pending} pending)` : ''}
      </Subtitle>
      <ErrorBox>{error}</ErrorBox>
      <NoticeBox>{notice}</NoticeBox>

      <Card>
        <View style={{ flexDirection: 'row', marginBottom: 8 }}>
          <Pill label="Topic" active={mode === 'topic'} onPress={() => setMode('topic')} />
          <Pill label="Write-Up" active={mode === 'writeup'} onPress={() => setMode('writeup')} />
        </View>
        {mode === 'topic' ? (
          <>
            <Input value={topic} onChangeText={setTopic} placeholder="Topic idea…" />
            <View style={{ flexDirection: 'row', marginTop: 10 }}>
              {[3, 4, 5].map((d) => <Pill key={d} label={`${d} min`} active={duration === d} onPress={() => setDuration(d)} />)}
            </View>
          </>
        ) : (
          <Input value={content} onChangeText={setContent} placeholder="Write your script…" multiline />
        )}
        <Button title="＋ Save Draft" onPress={add} />
      </Card>

      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
        <Muted style={{ color: theme.text, fontWeight: '800' }}>Saved ({drafts.length})</Muted>
        <Button title={syncing ? 'Syncing…' : `⟳ Sync${pending ? ` (${pending})` : ''}`} variant="secondary" onPress={sync} loading={syncing} disabled={!pending} style={{ marginTop: 0, minHeight: 40, paddingHorizontal: 14 }} />
      </View>

      {drafts.length === 0 && <Muted>No drafts yet.</Muted>}
      {drafts.slice().reverse().map((d) => (
        <Card key={d.id}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Muted style={{ color: d.synced ? theme.ok : theme.warn, fontWeight: '800', fontSize: 12 }}>
              {d.synced ? '✓ SYNCED' : '• PENDING'} · {d.mode === 'topic' ? 'Topic' : 'Write-Up'}
            </Muted>
            <Muted style={{ fontSize: 12 }} onPress={() => remove(d.id)}>🗑 Delete</Muted>
          </View>
          <Muted style={{ color: theme.text, marginTop: 6 }} numberOfLines={3}>
            {d.mode === 'topic' ? d.topic : d.content}
          </Muted>
        </Card>
      ))}
    </Screen>
  )
}
