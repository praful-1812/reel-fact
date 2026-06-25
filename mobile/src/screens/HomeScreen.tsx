import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import * as Clipboard from "expo-clipboard";

import { submitReel, checkHealth } from "../api/client";
import { colors, radius, spacing } from "../theme";

export function HomeScreen({
  apiBase,
  onSubmitted,
  onChangeApiBase,
}: {
  apiBase: string;
  onSubmitted: (jobId: number) => void;
  onChangeApiBase: (base: string) => void;
}) {
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showSettings, setShowSettings] = useState(false);
  const [baseInput, setBaseInput] = useState(apiBase);
  const [healthMsg, setHealthMsg] = useState<string | null>(null);

  const onPaste = async () => {
    const text = await Clipboard.getStringAsync();
    if (text) {
      setUrl(text.trim());
      setError(null);
    }
  };

  const onSubmit = async () => {
    setError(null);
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Paste an Instagram reel link first.");
      return;
    }
    setSubmitting(true);
    try {
      const job = await submitReel(apiBase, trimmed);
      onSubmitted(job.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  const onTestConnection = async () => {
    setHealthMsg("Checking…");
    try {
      const h = await checkHealth(baseInput);
      setHealthMsg(
        `✓ Connected · ${h.default_model} · ffmpeg ${h.ffmpeg_installed ? "ok" : "missing"}`
      );
      onChangeApiBase(baseInput.trim());
    } catch (e) {
      setHealthMsg(`✗ ${e instanceof Error ? e.message : "Failed"}`);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.logo}>🔎 Reel Fact</Text>
        <Text style={styles.tagline}>
          Paste an Instagram Reel link. We transcribe it and let AI agents fact-check what it
          claims.
        </Text>

        <View style={styles.inputCard}>
          <TextInput
            style={styles.input}
            value={url}
            onChangeText={(t) => {
              setUrl(t);
              setError(null);
            }}
            placeholder="https://www.instagram.com/reel/…"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
            multiline
          />
          <Pressable style={styles.pasteBtn} onPress={onPaste} hitSlop={8}>
            <Text style={styles.pasteText}>Paste</Text>
          </Pressable>
        </View>

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable
          style={[styles.submit, submitting && styles.submitDisabled]}
          onPress={onSubmit}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitText}>Check this reel</Text>
          )}
        </Pressable>

        <View style={styles.steps}>
          <Text style={styles.stepsTitle}>How it works</Text>
          {[
            "1.  We download the reel and pull out its audio",
            "2.  Whisper transcribes what's said",
            "3.  An agent extracts the factual claims",
            "4.  Each claim is verified and explained",
            "5.  You get a verdict + what's wrong",
          ].map((line) => (
            <Text key={line} style={styles.stepLine}>
              {line}
            </Text>
          ))}
        </View>

        {/* Backend settings (collapsible) */}
        <Pressable onPress={() => setShowSettings((s) => !s)} style={styles.settingsToggle}>
          <Text style={styles.settingsToggleText}>
            {showSettings ? "▾  Backend settings" : "▸  Backend settings"}
          </Text>
        </Pressable>

        {showSettings && (
          <View style={styles.settingsCard}>
            <Text style={styles.settingsLabel}>Backend URL</Text>
            <TextInput
              style={styles.settingsInput}
              value={baseInput}
              onChangeText={setBaseInput}
              placeholder="http://10.0.2.2:8000"
              placeholderTextColor={colors.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
            />
            <Pressable style={styles.testBtn} onPress={onTestConnection}>
              <Text style={styles.testText}>Test connection &amp; save</Text>
            </Pressable>
            {healthMsg && <Text style={styles.healthMsg}>{healthMsg}</Text>}
            <Text style={styles.hint}>
              Emulator: http://10.0.2.2:8000 · Real device: your computer&apos;s LAN IP (e.g.
              http://192.168.1.20:8000)
            </Text>
          </View>
        )}

        <Text style={styles.disclaimer}>
          Automated fact-checking is assistive, not authoritative. Always double-check important
          claims against trusted sources.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: {
    padding: spacing.xl,
    gap: spacing.lg,
  },
  logo: {
    color: colors.text,
    fontSize: 34,
    fontWeight: "900",
    marginTop: spacing.sm,
  },
  tagline: {
    color: colors.textMuted,
    fontSize: 15,
    lineHeight: 22,
  },
  inputCard: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    flexDirection: "row",
    alignItems: "flex-start",
    paddingRight: spacing.sm,
  },
  input: {
    flex: 1,
    color: colors.text,
    fontSize: 15,
    padding: spacing.lg,
    minHeight: 56,
  },
  pasteBtn: {
    alignSelf: "center",
    backgroundColor: colors.cardAlt,
    borderRadius: radius.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  pasteText: { color: colors.primary, fontWeight: "700" },
  error: { color: colors.danger, fontSize: 14 },
  submit: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.lg,
    alignItems: "center",
  },
  submitDisabled: { backgroundColor: colors.primaryDim },
  submitText: { color: "#fff", fontSize: 17, fontWeight: "800" },
  steps: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  stepsTitle: {
    color: colors.text,
    fontWeight: "800",
    fontSize: 15,
    marginBottom: spacing.xs,
  },
  stepLine: { color: colors.textMuted, fontSize: 14, lineHeight: 21 },
  settingsToggle: { paddingVertical: spacing.xs },
  settingsToggleText: { color: colors.primary, fontWeight: "700", fontSize: 14 },
  settingsCard: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  settingsLabel: { color: colors.textMuted, fontSize: 12, fontWeight: "700" },
  settingsInput: {
    color: colors.text,
    backgroundColor: colors.cardAlt,
    borderRadius: radius.sm,
    padding: spacing.md,
    fontSize: 14,
  },
  testBtn: {
    backgroundColor: colors.cardAlt,
    borderRadius: radius.sm,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  testText: { color: colors.primary, fontWeight: "700" },
  healthMsg: { color: colors.textMuted, fontSize: 13 },
  hint: { color: colors.textMuted, fontSize: 12, lineHeight: 18 },
  disclaimer: {
    color: colors.textMuted,
    fontSize: 12,
    lineHeight: 18,
    fontStyle: "italic",
    marginTop: spacing.sm,
  },
});
