import React from "react";
import { View, Text, StyleSheet } from "react-native";

import { Verdict } from "../api/client";
import { colors, radius, spacing, verdictColor, verdictLabel } from "../theme";

/** Large verdict banner shown at the top of a result. */
export function VerdictBadge({
  verdict,
  confidence,
}: {
  verdict?: Verdict | string | null;
  confidence?: number;
}) {
  const color = verdictColor(verdict);
  return (
    <View style={[styles.badge, { borderColor: color, backgroundColor: color + "22" }]}>
      <Text style={[styles.label, { color }]}>{verdictLabel(verdict)}</Text>
      {typeof confidence === "number" && (
        <Text style={styles.confidence}>{Math.round(confidence * 100)}% confidence</Text>
      )}
    </View>
  );
}

/** Small inline verdict pill used inside claim cards. */
export function VerdictPill({ verdict }: { verdict?: Verdict | string | null }) {
  const color = verdictColor(verdict);
  const text =
    typeof verdict === "string" ? verdict.charAt(0).toUpperCase() + verdict.slice(1) : "Unknown";
  return (
    <View style={[styles.pill, { backgroundColor: color + "22", borderColor: color }]}>
      <Text style={[styles.pillText, { color }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderWidth: 1,
    borderRadius: radius.lg,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    gap: spacing.xs,
  },
  label: {
    fontSize: 22,
    fontWeight: "800",
  },
  confidence: {
    color: colors.textMuted,
    fontSize: 13,
  },
  pill: {
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
    alignSelf: "flex-start",
  },
  pillText: {
    fontSize: 12,
    fontWeight: "700",
  },
});
