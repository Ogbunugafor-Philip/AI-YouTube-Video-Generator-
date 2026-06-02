import React, { useEffect, useState, useCallback } from 'react'
import { View, Image, RefreshControl, Linking, StyleSheet, TextInput } from 'react-native'
import { Screen, Title, Subtitle, Card, Button, Muted, ErrorBox, Pill } from '../components/UI'
import { theme, MODE_LABELS } from '../theme'
import { api } from '../api'

const fmtNum = (n) => (n == null ? '—' : Number(n).toLocaleString())
const fmtDate = (d) => { try { return new Date(d).toLocaleDateString() } catch { return d || '—' } }

export default function HistoryScreen() {
  const [videos, setVideos] = useState([])
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [search, setSearch] = useState('')
  const [mode, setMode] = useState('all')
  const [detail, setDetail] = useState(null)

  const load = useCallback(async () => {
    setError('')
    try {
      const r = await api.getHistory()
      setVideos(r.videos || [])
    } catch (e) { setError(e.message) }
  }, [])

  useEffect(() => { load() }, [load])

  const onRefresh = async () => { setRefreshing(true); await load(); setRefreshing(false) }

  async function open(jobId) {
    try { setDetail(await api.getHistoryDetail(jobId)) } catch (e) { setError(e.message) }
  }

  const filtered = videos.filter((v) => {
    if (mode !== 'all' && (v.mode || 'topic') !== mode) return false
    if (search.trim() && !(v.title || '').toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  if (detail) {
    return (
      <Screen>
        <Button title="‹ Back to list" variant="ghost" onPress={() => setDetail(null)} style={{ marginTop: 0 }} />
        <Title>{detail.title}</Title>
        <Subtitle>{MODE_LABELS[detail.mode] || 'Topic'} · {fmtDate(detail.date)} · {detail.duration_minutes} min</Subtitle>
        <View style={s.statRow}>
          {[['Views', detail.views], ['Likes', detail.likes], ['Comments', detail.comments]].map(([l, n]) => (
            <Card key={l} style={{ flex: 1, alignItems: 'center', marginHorizontal: 4 }}>
              <Muted style={{ color: theme.accent, fontSize: 20, fontWeight: '900' }}>{fmtNum(n)}</Muted>
              <Muted style={{ fontSize: 11 }}>{l}</Muted>
            </Card>
          ))}
        </View>
        <View style={s.statRow}>
          {[['Watch (min)', detail.watch_time_minutes], ['Avg View (s)', detail.avg_view_duration_sec], ['Retention %', detail.avg_view_percentage]].map(([l, n]) => (
            <Card key={l} style={{ flex: 1, alignItems: 'center', marginHorizontal: 4 }}>
              <Muted style={{ color: theme.text, fontSize: 16, fontWeight: '800' }}>{n == null ? '—' : n}</Muted>
              <Muted style={{ fontSize: 11 }}>{l}</Muted>
            </Card>
          ))}
        </View>
        {detail.youtube_url && <Button title="▶ Open on YouTube" variant="ghost" onPress={() => Linking.openURL(detail.youtube_url)} />}
        <Card><Muted style={{ color: theme.text, fontWeight: '800', marginBottom: 6 }}>Script</Muted><Muted style={{ lineHeight: 21 }}>{detail.script_text || '—'}</Muted></Card>
        <Muted style={{ color: theme.text, fontWeight: '800', marginBottom: 8 }}>Scenes ({detail.scenes?.length || 0})</Muted>
        {(detail.scenes || []).map((sc, i) => (
          <Card key={i} style={{ borderLeftWidth: 3, borderLeftColor: theme.accent }}>
            <Muted style={{ color: theme.accent, fontWeight: '800', fontSize: 11 }}>SCENE {sc.scene_number ?? i + 1}</Muted>
            <Muted style={{ color: theme.text, marginVertical: 4 }}>{sc.narration_text}</Muted>
            <Muted style={{ fontStyle: 'italic' }}>🎬 {sc.visual_description}</Muted>
          </Card>
        ))}
      </Screen>
    )
  }

  return (
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.accent} />}>
      <Title>Video History</Title>
      <Subtitle>Every video, with live YouTube stats.</Subtitle>
      <ErrorBox>{error}</ErrorBox>

      <TextInput
        value={search}
        onChangeText={setSearch}
        placeholder="Search by title…"
        placeholderTextColor={theme.muted}
        style={s.search}
      />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginBottom: 6 }}>
        {['all', 'topic', 'writeup', 'news'].map((m) => (
          <Pill key={m} label={m === 'all' ? 'All' : MODE_LABELS[m]} active={mode === m} onPress={() => setMode(m)} />
        ))}
      </View>

      {filtered.length === 0 && <Muted>No videos yet.</Muted>}
      {filtered.map((v) => (
        <Card key={v.job_id} onPress={() => open(v.job_id)} style={{ padding: 0, overflow: 'hidden' }}>
          {v.thumbnail_url ? (
            <Image source={{ uri: api.mediaUrl(v.thumbnail_url) }} style={s.thumb} resizeMode="cover" />
          ) : (
            <View style={[s.thumb, { alignItems: 'center', justifyContent: 'center' }]}><Muted>No thumbnail</Muted></View>
          )}
          <View style={{ padding: 14 }}>
            <Muted style={{ color: theme.text, fontWeight: '800', fontSize: 15 }} numberOfLines={2}>{v.title}</Muted>
            <Muted style={{ marginTop: 4 }}>{MODE_LABELS[v.mode] || 'Topic'} · {fmtDate(v.date)} · {v.duration_minutes} min</Muted>
            <View style={{ flexDirection: 'row', marginTop: 8 }}>
              <Muted style={{ marginRight: 16 }}>👁 {fmtNum(v.views)}</Muted>
              <Muted style={{ marginRight: 16 }}>👍 {fmtNum(v.likes)}</Muted>
              <Muted>💬 {fmtNum(v.comments)}</Muted>
            </View>
          </View>
        </Card>
      ))}
    </Screen>
  )
}

const s = StyleSheet.create({
  statRow: { flexDirection: 'row', marginBottom: 8, marginHorizontal: -4 },
  thumb: { width: '100%', aspectRatio: 16 / 9, backgroundColor: 'rgba(0,0,0,0.35)' },
  search: {
    backgroundColor: 'rgba(0,0,0,0.25)', borderColor: theme.border, borderWidth: 1, borderRadius: 12,
    color: theme.text, padding: 12, fontSize: 15, marginBottom: 12,
  },
})
