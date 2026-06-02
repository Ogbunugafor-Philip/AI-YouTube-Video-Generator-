import React from 'react'
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  StyleSheet,
} from 'react-native'
import { theme } from '../theme'

export function Screen({ children, scroll = true, refreshControl }) {
  const Container = scroll ? ScrollView : View
  return (
    <Container
      style={s.screen}
      contentContainerStyle={scroll ? s.scrollContent : null}
      refreshControl={refreshControl}
      keyboardShouldPersistTaps="handled"
    >
      {children}
    </Container>
  )
}

export function Title({ children }) {
  return <Text style={s.title}>{children}</Text>
}
export function Subtitle({ children }) {
  return <Text style={s.subtitle}>{children}</Text>
}
export function Muted({ children, style }) {
  return <Text style={[s.muted, style]}>{children}</Text>
}

export function Card({ children, style, onPress }) {
  if (onPress) {
    return (
      <TouchableOpacity activeOpacity={0.8} onPress={onPress} style={[s.card, style]}>
        {children}
      </TouchableOpacity>
    )
  }
  return <View style={[s.card, style]}>{children}</View>
}

export function Button({ title, onPress, variant = 'primary', disabled, loading, style }) {
  const vStyle =
    variant === 'secondary' ? s.btnSecondary : variant === 'ghost' ? s.btnGhost : s.btnPrimary
  const tStyle =
    variant === 'secondary' ? s.btnSecondaryText : variant === 'ghost' ? s.btnGhostText : s.btnPrimaryText
  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={onPress}
      disabled={disabled || loading}
      style={[s.btn, vStyle, (disabled || loading) && s.btnDisabled, style]}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? '#fff' : theme.accent} />
      ) : (
        <Text style={[s.btnText, tStyle]}>{title}</Text>
      )}
    </TouchableOpacity>
  )
}

export function Input({ value, onChangeText, placeholder, multiline, style }) {
  return (
    <TextInput
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={theme.muted}
      multiline={multiline}
      style={[s.input, multiline && s.inputMultiline, style]}
    />
  )
}

export function Pill({ label, active, onPress }) {
  return (
    <TouchableOpacity onPress={onPress} style={[s.pill, active && s.pillActive]}>
      <Text style={[s.pillText, active && s.pillTextActive]}>{label}</Text>
    </TouchableOpacity>
  )
}

export function ErrorBox({ children }) {
  if (!children) return null
  return (
    <View style={s.error}>
      <Text style={s.errorText}>{children}</Text>
    </View>
  )
}

export function NoticeBox({ children }) {
  if (!children) return null
  return (
    <View style={s.notice}>
      <Text style={s.noticeText}>{children}</Text>
    </View>
  )
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: theme.navy },
  scrollContent: { padding: 18, paddingBottom: 48 },
  title: { color: theme.text, fontSize: 24, fontWeight: '800', marginBottom: 4 },
  subtitle: { color: theme.muted, fontSize: 14, marginBottom: 18 },
  muted: { color: theme.muted, fontSize: 13 },
  card: {
    backgroundColor: theme.card,
    borderColor: theme.border,
    borderWidth: 1,
    borderRadius: theme.radius,
    padding: 16,
    marginBottom: 14,
  },
  btn: {
    minHeight: 52,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 18,
    marginTop: 10,
  },
  btnPrimary: { backgroundColor: theme.accent },
  btnSecondary: { backgroundColor: 'transparent', borderWidth: 1.5, borderColor: theme.accent },
  btnGhost: { backgroundColor: 'rgba(255,255,255,0.06)' },
  btnDisabled: { opacity: 0.45 },
  btnText: { fontSize: 16, fontWeight: '700' },
  btnPrimaryText: { color: '#fff' },
  btnSecondaryText: { color: theme.accent },
  btnGhostText: { color: theme.text },
  input: {
    backgroundColor: 'rgba(0,0,0,0.25)',
    borderColor: theme.border,
    borderWidth: 1,
    borderRadius: 12,
    color: theme.text,
    padding: 14,
    fontSize: 16,
  },
  inputMultiline: { minHeight: 160, textAlignVertical: 'top' },
  pill: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1,
    borderColor: theme.border,
    marginRight: 10,
    marginBottom: 10,
  },
  pillActive: { backgroundColor: 'rgba(233,69,96,0.18)', borderColor: theme.accent },
  pillText: { color: theme.muted, fontWeight: '700' },
  pillTextActive: { color: theme.text },
  error: {
    backgroundColor: 'rgba(233,69,96,0.15)',
    borderColor: theme.accent,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
  },
  errorText: { color: '#ffd5dd' },
  notice: {
    backgroundColor: 'rgba(46,204,113,0.15)',
    borderColor: theme.ok,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
  },
  noticeText: { color: '#d6ffe6' },
})
