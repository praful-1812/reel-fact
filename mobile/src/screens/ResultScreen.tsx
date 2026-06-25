import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Linking,
} from "react-native";

import { Job, getJob, isTerminal } from "../api/client";
import { colors, radius, spacing, verdictColor } from "../theme";
import { VerdictBadge } from "../components/VerdictBadge";
import { ClaimCard } from "../components/ClaimCard";
import { StageProgress } from "../components/StageProgress";

const POLL_OK_MS = 2500;
const POLL_RETRY_MS = 4000;

export function ResultScreen({
  apiBase,
  jobId,
  onBack,
}: {
  apiBase: string;
  jobId: number;
  onBack: () => void;
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const j = await getJob(apiBase, jobId);
        if (!active) return;
        setJob(j);
        setError(null);
        if (!isTerminal(j.status)) {
          timer = setTimeout(poll, POLL_OK_MS);
        }
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Connection problem");
        timer = setTimeout(poll, POLL_RETRY_MS);
      }
    };

    poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [apiBase, jobId]);

  const overall = job?.overall;
  const processing = job && !isTerminal(job.status);
  const failed = job?.status === "failed";

  return (
    <View style={styles.flex}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={onBack} hitSlop={10} style={styles.backBtn}>
          <Text style={styles.backText}>‹  Back</Text>
        </Pressable>
        <Text style={styles.headerTitle}>Reel Fact</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Still loading the first response */}
        {!job && !error && (
          <StageProgress stage="queued" stageIndex={0} stageTotal={7} />
        )}

        {/* Transient connection error before we have any job data */}
        {!job && error && (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Can&apos;t reach the backend</Text>
            <Text style={styles.errorBody}>{error}</Text>
            <Text style={styles.errorBody}>Retrying…</Text>
          </View>
        )}

        {/* Processing */}
        {processing && (
          <StageProgress
            stage={job.stage}
            stageIndex={job.stage_index}
            stageTotal={job.stage_total}
          />
        )}

        {/* Failed */}
        {failed && (
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>Couldn&apos;t check this reel</Text>
            <Text style={styles.errorBody}>{job.error || "Unknown error."}</Text>
            <Pressable style={styles.primaryBtn} onPress={onBack}>
              <Text style={styles.primaryBtnText}>Try another reel</Text>
            </Pressable>
          </View>
        )}

        {/* Done */}
        {job?.status === "done" && overall && (
          <>
            <VerdictBadge verdict={overall.verdict} confidence={overall.confidence} />

            {!!overall.summary && <Text style={styles.summary}>{overall.summary}</Text>}

            {/* What's wrong */}
            {overall.whats_wrong.length > 0 && (
              <View style={styles.section}>
                <Text style={styles.sectionTitle}>What&apos;s wrong</Text>
                {overall.whats_wrong.map((w, i) => (
                  <View key={i} style={styles.bulletRow}>
                    <Text style={[styles.bulletDot, { color: verdictColor("false") }]}>•</Text>
                    <Text style={styles.bulletText}>{w}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Source */}
            <View style={styles.sourceCard}>
              {!!job.source.uploader && (
                <Text style={styles.sourceUploader}>@{job.source.uploader}</Text>
              )}
              {!!job.source.caption && (
                <Text style={styles.sourceCaption} numberOfLines={4}>
                  {job.source.caption}
                </Text>
              )}
              <Pressable onPress={() => Linking.openURL(job.source.url)}>
                <Text style={styles.sourceLink}>Open original reel ↗</Text>
              </Pressable>
            </View>

            {/* Claims */}
            <Text style={styles.sectionTitle}>
              Claims checked ({job.claims.length})
            </Text>
            {job.claims.length === 0 && (
              <Text style={styles.muted}>
                No specific factual claims were found in this reel.
              </Text>
            )}
            <View style={{ gap: spacing.md }}>
              {job.claims.map((c, i) => (
                <ClaimCard key={i} claim={c} index={i} />
              ))}
            </View>

            {/* Transcript */}
            {!!job.transcript && (
              <View style={styles.transcriptWrap}>
                <Pressable onPress={() => setShowTranscript((s) => !s)}>
                  <Text style={styles.transcriptToggle}>
                    {showTranscript ? "▾  Hide transcript" : "▸  Show transcript"}
                  </Text>
                </Pressable>
                {showTranscript && <Text style={styles.transcript}>{job.transcript}</Text>}
              </View>
            )}

            <Pressable style={styles.primaryBtn} onPress={onBack}>
              <Text style={styles.primaryBtnText}>Check another reel</Text>
            </Pressable>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
  },
  backBtn: { minWidth: 64 },
  backText: { color: colors.primary, fontSize: 16, fontWeight: "700" },
  headerTitle: { color: colors.text, fontSize: 16, fontWeight: "800" },
  content: { padding: spacing.xl, gap: spacing.lg },
  summary: {
    color: colors.text,
    fontSize: 16,
    lineHeight: 24,
  },
  section: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
  },
  bulletRow: { flexDirection: "row", gap: spacing.sm },
  bulletDot: { fontSize: 16, fontWeight: "900" },
  bulletText: { color: colors.textMuted, fontSize: 14, lineHeight: 21, flex: 1 },
  sourceCard: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  sourceUploader: { color: colors.text, fontWeight: "700", fontSize: 15 },
  sourceCaption: { color: colors.textMuted, fontSize: 13, lineHeight: 19 },
  sourceLink: { color: colors.primary, fontWeight: "700", marginTop: spacing.xs },
  muted: { color: colors.textMuted, fontSize: 14 },
  transcriptWrap: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
  },
  transcriptToggle: { color: colors.primary, fontWeight: "700", fontSize: 14 },
  transcript: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 20,
    marginTop: spacing.md,
  },
  errorCard: {
    backgroundColor: colors.card,
    borderColor: colors.danger,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.md,
  },
  errorTitle: { color: colors.danger, fontSize: 17, fontWeight: "800" },
  errorBody: { color: colors.textMuted, fontSize: 14, lineHeight: 21 },
  primaryBtn: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing.lg,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  primaryBtnText: { color: "#fff", fontSize: 16, fontWeight: "800" },
});
