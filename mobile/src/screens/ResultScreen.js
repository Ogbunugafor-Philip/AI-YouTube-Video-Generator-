import React, { useState } from 'react'
import { View, Image, Linking, StyleSheet } from 'react-native'
import { Screen, Title, Subtitle, Card, Button, Muted, ErrorBox, NoticeBox } from '../components/UI'
import { theme } from '../theme'
import { api } from '../api'

export default function ResultScreen({ resetTo, session, setSession }) {
  const [bust, setBust] = useState(Date.now())
  const [regen, setRegen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [videoId, setVideoId] = useState(session.youtube_video_id || null)
  const [draftUrl, setDraftUrl] = useState(null)
  const [liveUrl, setLiveUrl] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const thumb = session.thumbnail_url ? `${api.mediaUrl(session.thumbnail_url)}?t=${bust}` : null

  async function regenerate() {
    setError(''); setRegen(true)
    try {
      await api.regenerateThumbnail(session.job_id, session.title)
      setBust(Date.now())
    } catch (e) { setError(e.message) } finally { setRegen(false) }
  }

  async function upload() {
    setError(''); setNotice(''); setUploading(true)
    try {
      const res = await api.uploadToYoutube(session.job_id)
      setVideoId(res.youtube_video_id)
      setDraftUrl(res.draft_url)
      setSession((s) => ({ ...s, youtube_video_id: res.youtube_video_id }))
      setNotice('Uploaded as a private YouTube draft.')
    } catch (e) { setError(e.message) } finally { setUploading(false) }
  }

  async function publish() {
    setError(''); setNotice(''); setPublishing(true)
    try {
      const res = await api.publish({ job_id: session.job_id, video_id: videoId })
      setLiveUrl(res.youtube_url)
      setNotice('Published! Your video is live on YouTube.')
    } catch (e) { setError(e.message) } finally { setPublishing(false) }
  }

  return (
    <Screen>
      <Title>🎉 {session.title}</Title>
      <Subtitle>Your video is ready.</Subtitle>
      <ErrorBox>{error}</ErrorBox>
      <NoticeBox>{notice}</NoticeBox>

      <Card>
        <Muted style={{ marginBottom: 8 }}>Thumbnail</Muted>
        {thumb ? <Image source={{ uri: thumb }} style={s.thumb} resizeMode="cover" /> : <Muted>Thumbnail not available.</Muted>}
      </Card>

      <Button title={regen ? 'Regenerating…' : '↻ Regenerate Thumbnail'} variant="secondary" onPress={regenerate} loading={regen} />
      <Button title="⬇ Download MP4" variant="ghost" onPress={() => Linking.openURL(api.downloadUrl(session.job_id))} />

      {!videoId ? (
        <Button title={uploading ? 'Uploading…' : '▶ Upload to YouTube (draft)'} onPress={upload} loading={uploading} />
      ) : !liveUrl ? (
        <>
          {draftUrl && <Button title="👁 Preview Draft" variant="ghost" onPress={() => Linking.openURL(draftUrl)} />}
          <Button title={publishing ? 'Publishing…' : '🚀 Publish to YouTube'} onPress={publish} loading={publishing} />
        </>
      ) : (
        <Button title="▶ View Live on YouTube" onPress={() => Linking.openURL(liveUrl)} />
      )}

      <Button title="+ Start New Video" variant="ghost" onPress={() => { setSession({}); resetTo('Home') }} />
    </Screen>
  )
}

const s = StyleSheet.create({
  thumb: { width: '100%', aspectRatio: 16 / 9, borderRadius: 10, backgroundColor: '#000' },
})
