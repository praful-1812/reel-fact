import React from "react";
import { View, Text, StyleSheet } from "react-native";

import { ClaimResult } from "../api/client";
import { colors, radius, spacing } from "../theme";
import { VerdictPill } from "./VerdictBadge";

/** A single fact-checked claim: the statement, its verdict, and the reasoning. */
export function ClaimCard({ claim, index }: { claim: ClaimResult; index: number }) {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.number}>#{index + 1}</Text>
        <VerdictPill verdict={claim.verdict} />
        <Text style={styles.confidence}>{Math.round(claim.confidence * 100)}%</Text>
      </View>

      <Text style={styles.claim}>{claim.claim}</Text>

      {!!claim.explanation && <Text style={styles.explanation}>{claim.explanation}</Text>}

      {!!claim.what_to_check && (
        <View style={styles.checkRow}>
          <Text style={styles.checkLabel}>How to verify  </Text>
          <Text style={styles.checkText}>{claim.what_to_check}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  number: {
    color: colors.textMuted,
    fontWeight: "700",
    fontSize: 13,
  },
  confidence: {
    marginLeft: "auto",
    color: colors.textMuted,
    fontSize: 12,
  },
  claim: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "600",
    lineHeight: 22,
  },
  explanation: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  checkRow: {
    marginTop: spacing.xs,
    backgroundColor: colors.cardAlt,
    borderRadius: radius.sm,
    padding: spacing.sm,
  },
  checkLabel: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  checkText: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 19,
  },
});
