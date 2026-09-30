import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback } from "react";

import { PagedStoryList } from "../components/PagedStoryList";
import { getTopic } from "../lib/api";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "Topic">;

export function TopicScreen({ route }: Props) {
  const { slug } = route.params;
  const fetchPage = useCallback((cursor?: string) => getTopic(slug, cursor), [slug]);

  return (
    <PagedStoryList
      fetchPage={fetchPage}
      loadingLabel="Loading topic"
      errorLabel="Couldn't load this topic."
      emptyLabel="No stories in this topic yet."
    />
  );
}
