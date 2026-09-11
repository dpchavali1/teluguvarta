import type { NavigatorScreenParams } from "@react-navigation/native";

export type MainTabParamList = {
  Home: undefined;
  Search: undefined;
  Saved: undefined;
  Notifications: undefined;
  Settings: undefined;
};

export type RootStackParamList = {
  Onboarding: undefined;
  Main: NavigatorScreenParams<MainTabParamList>;
  Topic: { slug: string; name?: string };
  TopicsIndex: undefined;
  StoryDetail: { slug: string };
  NotificationPreferences: undefined;
  Language: undefined;
  Privacy: undefined;
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
