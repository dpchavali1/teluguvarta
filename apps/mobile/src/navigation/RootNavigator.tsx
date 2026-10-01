import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";

import { LanguageScreen } from "../screens/LanguageScreen";
import { LatestScreen } from "../screens/LatestScreen";
import { NotificationPreferencesScreen } from "../screens/NotificationPreferencesScreen";
import { NotificationsScreen } from "../screens/NotificationsScreen";
import { OnboardingScreen } from "../screens/OnboardingScreen";
import { HiddenTopicsScreen } from "../screens/HiddenTopicsScreen";
import { PrivacyScreen } from "../screens/PrivacyScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { StoryDetailScreen } from "../screens/StoryDetailScreen";
import { TopicScreen } from "../screens/TopicScreen";
import { getOnboarded } from "../lib/storage";
import { MainTabs } from "./MainTabs";
import type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const [onboarded, setOnboarded] = useState<boolean | null>(null);

  useEffect(() => {
    getOnboarded().then(setOnboarded);
  }, []);

  if (onboarded === null) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator accessibilityLabel="Loading" />
      </View>
    );
  }

  return (
    <Stack.Navigator initialRouteName={onboarded ? "Main" : "Onboarding"}>
      <Stack.Screen name="Onboarding" component={OnboardingScreen} options={{ headerShown: false }} />
      <Stack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
      <Stack.Screen name="Topic" component={TopicScreen} options={({ route }) => ({ title: route.params.name ?? "Topic" })} />
      <Stack.Screen name="Latest" component={LatestScreen} options={{ title: "Latest" }} />
      <Stack.Screen name="StoryDetail" component={StoryDetailScreen} options={{ title: "Story" }} />
      <Stack.Screen name="Notifications" component={NotificationsScreen} options={{ title: "Notifications" }} />
      <Stack.Screen
        name="NotificationPreferences"
        component={NotificationPreferencesScreen}
        options={{ title: "Notification preferences" }}
      />
      <Stack.Screen name="Language" component={LanguageScreen} options={{ title: "Language" }} />
      <Stack.Screen name="Profile" component={ProfileScreen} options={{ title: "Your profile" }} />
      <Stack.Screen name="Privacy" component={PrivacyScreen} options={{ title: "Privacy" }} />
      <Stack.Screen name="HiddenTopics" component={HiddenTopicsScreen} options={{ title: "Hidden topics" }} />
    </Stack.Navigator>
  );
}
