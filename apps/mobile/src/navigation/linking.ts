import type { LinkingOptions } from "@react-navigation/native";

import { siteUrl } from "../lib/api";
import type { RootStackParamList } from "./types";

// Design-review fix: sharing a story produced a plain https:// URL that
// couldn't reopen the app even when installed — no scheme/linking config
// existed at all. This wires path -> screen mapping for both the custom
// `tte://` scheme (plus the legacy teluguglobal scheme) and the web origin (works once
// iOS associatedDomains / Android intentFilters + the corresponding
// apple-app-site-association / assetlinks.json are added — that needs the
// real Apple Team ID and Android signing-cert fingerprint, which don't
// exist yet pre-App-Store-Connect/Play-Console registration; deliberately
// not fabricated here). Story/topic slugs map 1:1 with apps/web's routes
// (storyUrl/getTopic), so the same shared link resolves the same way on
// both surfaces.
export const linking: LinkingOptions<RootStackParamList> = {
  prefixes: ["tte://", "teluguglobal://", siteUrl()],
  config: {
    // A cold-start link builds the stack from the path alone, so without this
    // a shared story opened with nothing under it: no back arrow, and Back
    // left the app. Main sits under every linked screen.
    initialRouteName: "Main",
    screens: {
      Main: {
        screens: {
          Home: "",
          Search: "search",
          Saved: "saved",
        },
      },
      Topic: "topic/:slug",
      Latest: "latest",
      StoryDetail: "story/:slug",
    },
  },
};
