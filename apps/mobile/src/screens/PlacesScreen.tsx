import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { getPlace, MAX_FOLLOWED_PLACES, PLACES, type Place } from "@teluguvarta/domain";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AccessibilityInfo, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { syncSavedStories } from "../lib/notificationSync";
import { getFollowedPlaces, saveFollowedPlaces, type FollowedPlace } from "../lib/storage";
import type { RootStackParamList } from "../navigation/types";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

const KIND_LABEL: Record<Place["kind"], string> = { COUNTRY: "Country", STATE: "State", DISTRICT: "District", CITY: "City" };
const SUGGESTION_LIMIT = 30;

function placeLine(place: Place): string {
  return `${place.nameEn} · ${place.nameTe}`;
}

// P03/ADR-043: explicit, multi-place follows chosen from the catalog (no GPS,
// no free text). Follows stay on this device; only ids and the per-place
// alert switch sync, and only so the server can send place alerts.
export function PlacesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const [followed, setFollowed] = useState<FollowedPlace[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getFollowedPlaces().then(setFollowed).catch(() => {});
  }, []);

  const persist = useCallback(async (next: FollowedPlace[]) => {
    setFollowed(await saveFollowedPlaces(next));
    syncSavedStories(); // best-effort; local storage stays the source of truth
  }, []);

  const followedIds = useMemo(() => new Set(followed.map((p) => p.placeId)), [followed]);
  const full = followed.length >= MAX_FOLLOWED_PLACES;

  const suggestions = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return PLACES.filter((p) => !followedIds.has(p.id))
      .filter((p) => !needle || p.nameEn.toLowerCase().includes(needle) || p.nameTe.includes(query.trim()))
      .slice(0, SUGGESTION_LIMIT);
  }, [query, followedIds]);

  function follow(place: Place) {
    if (full) return;
    persist([...followed, { placeId: place.id, alerts: false }]);
    AccessibilityInfo.announceForAccessibility(`Following ${place.nameEn}.`);
  }

  function unfollow(place: Place) {
    persist(followed.filter((p) => p.placeId !== place.id));
    AccessibilityInfo.announceForAccessibility(`Stopped following ${place.nameEn}.`);
  }

  function setAlerts(placeId: string, alerts: boolean) {
    persist(followed.map((p) => (p.placeId === placeId ? { ...p, alerts } : p)));
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.intro}>
        Follow up to {MAX_FOLLOWED_PLACES} places to see their stories first. Following a state or country also
        matches stories tagged in its districts and cities. Telugu-language news is the same for everyone.
      </Text>

      <Text style={styles.groupLabel} accessibilityRole="header">
        {`FOLLOWING (${followed.length}/${MAX_FOLLOWED_PLACES})`}
      </Text>
      {followed.length === 0 ? (
        <Text style={styles.hint}>You don't follow any places yet.</Text>
      ) : (
        <View style={styles.group}>
          {followed.map((entry, i) => {
            const place = getPlace(entry.placeId);
            if (!place) return null;
            return (
              <View key={entry.placeId} style={[styles.followRow, i < followed.length - 1 && styles.rowDivider]}>
                <Pressable
                  onPress={() => navigation.navigate("PlaceStories", { placeId: place.id })}
                  accessibilityRole="button"
                  accessibilityLabel={`Stories for ${place.nameEn}`}
                  style={styles.nameButton}
                >
                  <Text style={styles.rowLabel}>{placeLine(place)}</Text>
                  <Text style={styles.rowMeta}>{KIND_LABEL[place.kind]}</Text>
                </Pressable>
                <View style={styles.alertGroup}>
                  <Text style={styles.rowMeta}>Alerts</Text>
                  <Switch
                    value={entry.alerts}
                    onValueChange={(value) => setAlerts(entry.placeId, value)}
                    accessibilityLabel={`Alerts for ${place.nameEn}`}
                  />
                </View>
                <Pressable
                  onPress={() => unfollow(place)}
                  accessibilityRole="button"
                  accessibilityLabel={`Stop following ${place.nameEn}`}
                  style={styles.button}
                >
                  <Text style={styles.buttonText}>Remove</Text>
                </Pressable>
              </View>
            );
          })}
        </View>
      )}

      <Text style={styles.groupLabel} accessibilityRole="header">ADD A PLACE</Text>
      {full && <Text style={styles.hint}>You're following the maximum. Remove a place to add another.</Text>}
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search places (English or తెలుగు)"
        placeholderTextColor={ui.textSecondary}
        accessibilityLabel="Search places"
        autoCorrect={false}
        style={styles.input}
      />
      <View style={styles.group}>
        {suggestions.length === 0 ? (
          <Text style={[styles.hint, styles.pad]}>No places match.</Text>
        ) : (
          suggestions.map((place, i) => (
            <View key={place.id} style={[styles.followRow, i < suggestions.length - 1 && styles.rowDivider]}>
              <View style={styles.nameButton}>
                <Text style={styles.rowLabel}>{placeLine(place)}</Text>
                <Text style={styles.rowMeta}>{KIND_LABEL[place.kind]}</Text>
              </View>
              <Pressable
                onPress={() => follow(place)}
                disabled={full}
                accessibilityRole="button"
                accessibilityLabel={`Follow ${place.nameEn}`}
                accessibilityState={{ disabled: full }}
                style={[styles.button, full && styles.disabled]}
              >
                <Text style={styles.buttonText}>Follow</Text>
              </Pressable>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    content: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xl },
    intro: { ...typography.body, color: ui.textSecondary },
    hint: { ...typography.body, color: ui.textSecondary },
    pad: { padding: spacing.md },
    groupLabel: { ...typography.meta, color: ui.textSecondary, fontWeight: "700" },
    group: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderSubtle,
      overflow: "hidden",
    },
    followRow: {
      minHeight: 56,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.xs,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
    nameButton: { flex: 1, minHeight: 44, justifyContent: "center" },
    rowLabel: { ...typography.body, color: colors.text, flexShrink: 1 },
    rowMeta: { ...typography.meta, color: ui.textSecondary },
    alertGroup: { alignItems: "center" },
    input: {
      minHeight: 44,
      paddingHorizontal: spacing.md,
      borderRadius: radius.md,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
      color: colors.text,
      backgroundColor: colors.surface,
    },
    button: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: spacing.md,
      borderRadius: radius.md,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    disabled: { opacity: 0.4 },
    buttonText: { color: colors.text, fontWeight: "600" },
  });
}
