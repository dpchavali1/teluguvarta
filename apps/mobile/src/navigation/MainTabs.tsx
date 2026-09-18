import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import React from "react";
import { Text } from "react-native";

import { LanguageToggle } from "../components/LanguageToggle";
import { HomeScreen } from "../screens/HomeScreen";
import { SavedScreen } from "../screens/SavedScreen";
import { SearchScreen } from "../screens/SearchScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { TopicsIndexScreen } from "../screens/TopicsIndexScreen";
import { useAppTheme } from "../theme/useAppTheme";
import type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

// Plain-text glyphs (no icon-library dependency, per ADR-008) rendered via
// the system emoji font, so they're free and consistent on iOS + Android.
// Design review (2026-09-10) flagged this as visually unfinished and
// recommended @expo/vector-icons; re-attempted here and it installs
// cleanly in apps/mobile alone, but pulls in a second @types/react
// resolution that breaks apps/web's and apps/admin's `next build` type
// checking repo-wide (LayoutProps<"/"> "bigint is not assignable to
// ReactNode" — confirmed by reverting the install and rebuilding both
// clean). Not safe to add without a workspace-wide @types/react version
// audit first; see PROGRESS.md.
const TAB_GLYPHS: Record<keyof MainTabParamList, string> = {
  Home: "⌂",
  Search: "⌕",
  Saved: "♡",
  Topics: "▤",
  Settings: "☰",
};

export function MainTabs() {
  // ADR-014: the nav chrome (tab bar + per-tab header) previously read the
  // static light-scheme `colors` export directly, so it never responded to
  // system dark mode at all — a functional bug, not a styling gap.
  const { colors } = useAppTheme();

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: true,
        // Ink for active/emphasized, faint for inactive — matches web's
        // nav convention of reserving the accent color for fills/rules,
        // not small foreground text or icons (low contrast on light bone).
        tabBarActiveTintColor: colors.text,
        tabBarInactiveTintColor: colors.faint,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        headerStyle: { backgroundColor: colors.surface },
        headerTitleStyle: { color: colors.text },
        // Design-review fix: language was two taps deep in Settings with
        // no persistent affordance. One tap from every main tab now,
        // matching web's header-level placement.
        headerRight: () => <LanguageToggle />,
        tabBarIcon: ({ color }) => (
          <Text style={{ fontSize: 20, color }}>{TAB_GLYPHS[route.name as keyof MainTabParamList]}</Text>
        ),
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ tabBarAccessibilityLabel: "Home" }} />
      <Tab.Screen name="Search" component={SearchScreen} options={{ tabBarAccessibilityLabel: "Search" }} />
      <Tab.Screen name="Saved" component={SavedScreen} options={{ tabBarAccessibilityLabel: "Saved" }} />
      <Tab.Screen
        name="Topics"
        component={TopicsIndexScreen}
        options={{ tabBarAccessibilityLabel: "Topics" }}
      />
      <Tab.Screen name="Settings" component={SettingsScreen} options={{ tabBarAccessibilityLabel: "Settings" }} />
    </Tab.Navigator>
  );
}
