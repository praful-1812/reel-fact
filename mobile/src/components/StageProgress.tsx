import React from "react";
import { View, Text, StyleSheet, ActivityIndicator } from "react-native";

import { colors, radius, spacing } from "../theme";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued…",
  downloading: "Downloading the reel…",
  transcribing: "Transcribing the audio…",
  extracting_claims: "Finding factual claims…",
  verifying: "Verifying each claim…",
  synthesizing: "Writing the verdict…",
  done: "Done",
  failed: "Failed",
};

/** Animated-feeling progress block shown while a job is processing. */
export function StageProgress({
  stage,
  stageIndex,
  stageTotal,
}: {
  stage: string;
  stageIndex: number;
  stageTotal: number;
}) {
  const pct = stageTotal > 0 ? Math.min(1, Math.max(0, stageIndex / (stageTotal - 1))) : 0;
  const label = STAGE_LABELS[stage] ?? stage;

  return (
    <View style={styles.container}>
      <ActivityIndicator color={colors.primary} size="large" />
      <Text style={styles.label}>{label}</Text>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${Math.round(pct * 100)}%` }]} />
      </View>
      <Text style={styles.step}>
        Step {Math.min(stageIndex + 1, stageTotal)} of {stageTotal}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.xxl,
  },
  label: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "600",
  },
  track: {
    width: "100%",
    height: 8,
    backgroundColor: colors.cardAlt,
    borderRadius: radius.pill,
    overflow: "hidden",
  },
  fill: {
    height: "100%",
    backgroundColor: colors.primary,
    borderRadius: radius.pill,
  },
  step: {
    color: colors.textMuted,
    fontSize: 13,
  },
});
