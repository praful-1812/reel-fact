import React, { useState } from "react";
import { SafeAreaView, StyleSheet, Platform, StatusBar } from "react-native";
import { StatusBar as ExpoStatusBar } from "expo-status-bar";

import { HomeScreen } from "./src/screens/HomeScreen";
import { ResultScreen } from "./src/screens/ResultScreen";
import { DEFAULT_API_BASE } from "./src/api/client";
import { colors } from "./src/theme";

/**
 * Root component. A tiny state machine swaps between the Home screen (paste a
 * link) and the Result screen (poll + show the verdict) — no nav library needed
 * for two screens, which keeps the dependency surface small.
 */
export default function App() {
  const [apiBase, setApiBase] = useState<string>(DEFAULT_API_BASE);
  const [jobId, setJobId] = useState<number | null>(null);

  return (
    <SafeAreaView style={styles.safe}>
      <ExpoStatusBar style="light" />
      {jobId === null ? (
        <HomeScreen
          apiBase={apiBase}
          onChangeApiBase={setApiBase}
          onSubmitted={(id) => setJobId(id)}
        />
      ) : (
        <ResultScreen apiBase={apiBase} jobId={jobId} onBack={() => setJobId(null)} />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.bg,
    // react-native's SafeAreaView doesn't pad the Android status bar, so do it manually.
    paddingTop: Platform.OS === "android" ? StatusBar.currentHeight ?? 0 : 0,
  },
});
