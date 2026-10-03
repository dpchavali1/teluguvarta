import { applyPreset, PERSONA_PRESETS, removePreset, type PersonaPresetId, type PersonaState } from "@teluguvarta/domain";
import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// P01: toggling a preset only sets/unsets the explicit choices it owns
// (see packages/domain/personas.ts); persisting is the caller's job.
export function PersonaPresetPicker({
  state,
  onChange,
}: {
  state: PersonaState;
  onChange: (next: PersonaState) => void;
}) {
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  return (
    <View style={styles.wrap}>
      {PERSONA_PRESETS.map((preset) => {
        const selected = Boolean(state.applied[preset.id]);
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
            style={[styles.chip, selected && styles.chipSelected]}
          >
            <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{preset.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    chip: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: 14,
      borderRadius: 22,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.bg,
    },
    chipSelected: { backgroundColor: ui.actionPrimary, borderColor: ui.actionPrimary },
    chipText: { color: colors.text, fontSize: 15 },
    chipTextSelected: { color: ui.actionPrimaryText, fontWeight: "600" },
  });
}
