import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { placeName } from "@teluguvarta/domain";
import React, { useCallback } from "react";

import { PagedStoryList } from "../components/PagedStoryList";
import { listStories } from "../lib/api";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "PlaceStories">;

// ADR-043: stories tagged at or beneath the place. A place with no stories
// says so; it never silently falls back to other places.
export function PlaceStoriesScreen({ route }: Props) {
  const { placeId } = route.params;
  const name = placeName(placeId, "en");
  const fetchPage = useCallback(
    async (cursor?: string) => {
      const page = await listStories({ place: placeId, cursor });
      return { stories: page.items, next_cursor: page.next_cursor };
    },
    [placeId]
  );

  return (
    <PagedStoryList
      fetchPage={fetchPage}
      loadingLabel={`Loading stories for ${name}`}
      errorLabel={`Couldn't load stories for ${name}.`}
      emptyLabel={`No stories are tagged for ${name} yet. We don't fill this with other places.`}
    />
  );
}
