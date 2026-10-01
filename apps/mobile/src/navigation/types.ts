import type { NavigatorScreenParams } from "@react-navigation/native";

// ADR-014 TopicControl: Topics needed an unmistakable destination, not a
// row buried inside Settings — it now takes the tab slot Notifications used
// to hold. Notifications (the "nothing to deliver into yet" inbox shell)
// moves to a Settings row + pushed stack screen instead, which also cuts
// the tab bar back down from a busy 5-tabs-plus-header-language-control to
// a tab bar that only carries first-class reading destinations.
export type MainTabParamList = {
  Home: undefined;
  Search: undefined;
  Saved: undefined;
  Topics: undefined;
  Settings: undefined;
};

export type RootStackParamList = {
  Onboarding: undefined;
  Main: NavigatorScreenParams<MainTabParamList>;
  Topic: { slug: string; name?: string };
  Latest: undefined;
  StoryDetail: { slug: string };
  Notifications: undefined;
  NotificationPreferences: undefined;
  Language: undefined;
  Privacy: undefined;
  Profile: undefined;
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
