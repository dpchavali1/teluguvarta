import Ionicons from "@expo/vector-icons/Ionicons";
import { applyPreset, PERSONA_PRESETS, removePreset, type PersonaPresetId, type PersonaState } from "@teluguvarta/domain";
import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { radius } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const PRESET_ICONS: Record<PersonaPresetId, IconName> = {
  student: "school-outline",
  "h1b-green-card": "document-text-outline",
  "family-back-home": "home-outline",
  farmer: "leaf-outline",
  investor: "trending-up-outline",
  techie: "laptop-outline",
  "movie-fan": "film-outline",
};

// P01: toggling a preset only sets/unsets the explicit choices it owns
// (see packages/domain/personas.ts); persisting is the caller's job.
export function PersonaPresetPicker({
  state,
  onChange,
  embedded,
}: {
  state: PersonaState;
  onChange: (next: PersonaState) => void;
  /** Inside another card: drop this picker's own border and background. */
  embedded?: boolean;
}) {
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  return (
    <View style={embedded ? undefined : styles.group}>
      {PERSONA_PRESETS.map((preset, i) => {
        const selected = Boolean(state.applied[preset.id]);
        const last = i === PERSONA_PRESETS.length - 1;
        return (
          <Pressable
            key={preset.id}
            onPress={() =>
              onChange(selected ? removePreset(state, preset.id as PersonaPresetId) : applyPreset(state, preset.id as PersonaPresetId))
            }
            accessibilityRole="checkbox"
            accessibilityState={{ checked: selected }}
            accessibilityLabel={preset.label}
            accessibilityHint={preset.description}
            style={[styles.row, !last && styles.rowDivider]}
          >
            <View style={[styles.iconWrap, selected && styles.iconWrapSelected]}>
              <Ionicons
                name={PRESET_ICONS[preset.id as PersonaPresetId]}
                size={20}
                color={selected ? ui.actionPrimaryText : ui.actionPrimary}
                accessible={false}
              />
            </View>
            <View style={styles.text}>
              <Text style={styles.label}>{preset.label}</Text>
              <Text style={styles.description}>{preset.description}</Text>
            </View>
            <View style={[styles.check, selected && styles.checkSelected]}>
              {selected ? <Ionicons name="checkmark" size={16} color={ui.actionPrimaryText} accessible={false} /> : null}
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    group: {
      backgroundColor: colors.surface,
      borderRadius: radius.card,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderSubtle,
      overflow: "hidden",
    },
    row: { flexDirection: "row", alignItems: "center", gap: 12, minHeight: 64, paddingHorizontal: 14, paddingVertical: 10 },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
    iconWrap: {
      width: 36,
      height: 36,
      borderRadius: 18,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: ui.actionPrimarySoft,
    },
    iconWrapSelected: { backgroundColor: ui.actionPrimary },
    text: { flex: 1, gap: 2 },
    label: { color: colors.text, fontSize: 16, fontWeight: "600" },
    description: { color: ui.textTertiary, fontSize: 13, lineHeight: 18 },
    check: {
      width: 24,
      height: 24,
      borderRadius: 12,
      borderWidth: 1.5,
      borderColor: colors.border,
      alignItems: "center",
      justifyContent: "center",
    },
    checkSelected: { backgroundColor: ui.actionPrimary, borderColor: ui.actionPrimary },
  });
}
