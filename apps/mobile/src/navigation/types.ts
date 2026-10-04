import type { NavigatorScreenParams } from "@react-navigation/native";

// ADR-014 TopicControl: Topics needed an unmistakable destination, not a
// row buried inside Settings — it now takes the tab slot Notifications used
// to hold. Alert settings live behind one Settings row.
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
  Language: undefined;
  Privacy: undefined;
  Profile: undefined;
  HiddenTopics: undefined;
  Places: undefined;
  MySignals: undefined;
  PlaceStories: { placeId: string };
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
