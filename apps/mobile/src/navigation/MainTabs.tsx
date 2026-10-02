import Ionicons from "@expo/vector-icons/Ionicons";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import React from "react";

import { LanguageToggle } from "../components/LanguageToggle";
import { HomeScreen } from "../screens/HomeScreen";
import { SavedScreen } from "../screens/SavedScreen";
import { SearchScreen } from "../screens/SearchScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { TopicsIndexScreen } from "../screens/TopicsIndexScreen";
import { useAppTheme } from "../theme/useAppTheme";
import type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

// Review R10: vector icons replace the old text glyphs (⌂ ⌕ ♡ ▤ ☰), which
// depended on each device's system font. @expo/vector-icons was blocked
// earlier by a second @types/react resolution breaking the Next builds; with
// the workspace's current types it installs with no extra resolution and
// apps/web + apps/admin still build. Filled when focused, outline otherwise.
type IconName = React.ComponentProps<typeof Ionicons>["name"];
const TAB_ICONS: Record<keyof MainTabParamList, [focused: IconName, unfocused: IconName]> = {
  Home: ["home", "home-outline"],
  Search: ["search", "search-outline"],
  Saved: ["bookmark", "bookmark-outline"],
  Topics: ["grid", "grid-outline"],
  Settings: ["settings", "settings-outline"],
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
        // Indigo marks the active destination in both contrast-checked modes.
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.faint,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        headerStyle: { backgroundColor: colors.surface },
        headerTitleStyle: { color: colors.text },
        // ADR-014 step 5: the header has a fixed height, so a Dynamic Type
        // title clipped at the largest sizes. Native iOS nav-bar titles
        // don't scale either; screen content still does.
        headerTitleAllowFontScaling: false,
        // Design-review fix: language was two taps deep in Settings with
        // no persistent affordance. One tap from every main tab now,
        // matching web's header-level placement.
        headerRight: () => <LanguageToggle />,
        tabBarIcon: ({ color, focused, size }) => {
          const [active, inactive] = TAB_ICONS[route.name as keyof MainTabParamList];
          return <Ionicons name={focused ? active : inactive} size={size} color={color} />;
        },
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
