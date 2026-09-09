import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import React from "react";

import { HomeScreen } from "../screens/HomeScreen";
import { NotificationsScreen } from "../screens/NotificationsScreen";
import { SavedScreen } from "../screens/SavedScreen";
import { SearchScreen } from "../screens/SearchScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

export function MainTabs() {
  return (
    <Tab.Navigator screenOptions={{ headerShown: true }}>
      <Tab.Screen name="Home" component={HomeScreen} options={{ tabBarAccessibilityLabel: "Home" }} />
      <Tab.Screen name="Search" component={SearchScreen} options={{ tabBarAccessibilityLabel: "Search" }} />
      <Tab.Screen name="Saved" component={SavedScreen} options={{ tabBarAccessibilityLabel: "Saved" }} />
      <Tab.Screen
        name="Notifications"
        component={NotificationsScreen}
        options={{ tabBarAccessibilityLabel: "Notifications" }}
      />
      <Tab.Screen name="Settings" component={SettingsScreen} options={{ tabBarAccessibilityLabel: "Settings" }} />
    </Tab.Navigator>
  );
}
