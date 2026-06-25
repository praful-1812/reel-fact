/**
 * Central theme: dark palette, spacing, radii, and verdict color mapping.
 */
import { Verdict } from "./api/client";

export const colors = {
  bg: "#0B1020",
  card: "#151B2E",
  cardAlt: "#1C2740",
  border: "#27324D",
  text: "#E6EAF2",
  textMuted: "#9AA6C0",
  primary: "#6C5CE7",
  primaryDim: "#4B3FB0",

  // Verdict palette
  success: "#22C55E",
  danger: "#EF4444",
  warning: "#F59E0B",
  neutral: "#64748B",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
} as const;

/** Map a verdict to its accent color. */
export function verdictColor(verdict?: Verdict | string | null): string {
  switch (verdict) {
    case "true":
      return colors.success;
    case "false":
      return colors.danger;
    case "misleading":
      return colors.warning;
    default:
      return colors.neutral;
  }
}

/** Human-friendly label + emoji for a verdict. */
export function verdictLabel(verdict?: Verdict | string | null): string {
  switch (verdict) {
    case "true":
      return "✅  Looks True";
    case "false":
      return "❌  False";
    case "misleading":
      return "⚠️  Misleading";
    default:
      return "❔  Unverifiable";
  }
}
