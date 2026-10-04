import React, { useState } from "react";
import { Modal, Pressable, ScrollView, Text, TextInput, View } from "react-native";

import type { StoryOut } from "../lib/api";
import { cancelReadLater, scheduleReadLater } from "../lib/readLater";
import {
  addCollection, MAX_COLLECTION_NAME, MAX_COLLECTIONS, MAX_NOTE_LENGTH, REMINDER_PRESETS, reminderTime,
  setNote, setReminder, toggleMembership, type SavedExtras,
} from "../lib/savedExtras";
import { useStoryCache } from "../lib/StoryCacheContext";
import { radius, spacing } from "../theme/tokens";
import { useAppTheme } from "../theme/useAppTheme";

// P06 / ADR-044: lists, note and read-later reminder for one bookmark.
export function SavedOrganizer({ story, extras }: { story: StoryOut; extras: SavedExtras }) {
  const { updateExtras } = useStoryCache();
  const { colors, ui } = useAppTheme();
  const [open, setOpen] = useState(false);
  const [note, setNoteText] = useState(extras.notes[story.id] ?? "");
  const [newList, setNewList] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const headline = (story.variants.en ?? Object.values(story.variants)[0])?.headline ?? story.canonical_slug;
  const reminder = extras.reminders[story.id];
  const memberOf = extras.membership[story.id] ?? [];

  const chip = (label: string, selected: boolean, onPress: () => void) => (
    <Pressable key={label} onPress={onPress} accessibilityRole="button" accessibilityState={{ selected }} accessibilityLabel={label}
      style={{ minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.md, borderRadius: radius.pill, borderWidth: 1,
        borderColor: ui.borderControl, backgroundColor: selected ? ui.actionPrimary : "transparent" }}>
      <Text style={{ fontWeight: "600", color: selected ? ui.actionPrimaryText : colors.text }}>{label}</Text>
    </Pressable>
  );

  const remind = async (days: number) => {
    const at = reminderTime(new Date(), days);
    if (reminder) await cancelReadLater(reminder.notificationId);
    const notificationId = await scheduleReadLater(story.canonical_slug, headline, at);
    if (!notificationId) {
      updateExtras((current) => setReminder(current, story.id, null));
      setStatus("Turn on notifications in system settings to get reminders.");
      return;
    }
    updateExtras((current) => setReminder(current, story.id, { at, notificationId }));
    setStatus(null);
  };
  const clearReminder = async () => {
    if (reminder) await cancelReadLater(reminder.notificationId);
    updateExtras((current) => setReminder(current, story.id, null));
  };
  const summary = [
    memberOf.length ? `${memberOf.length} list${memberOf.length > 1 ? "s" : ""}` : null,
    extras.notes[story.id] ? "note" : null,
    reminder ? `reminder ${new Date(reminder.at).toLocaleDateString()}` : null,
  ].filter(Boolean).join(" · ");

  return (
    <View style={{ paddingHorizontal: spacing.md, paddingBottom: spacing.sm, flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
      <Pressable onPress={() => { setNoteText(extras.notes[story.id] ?? ""); setOpen(true); }} accessibilityRole="button"
        accessibilityLabel={`Organize: ${headline}`}
        style={{ minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.md, borderRadius: radius.pill, borderWidth: 1, borderColor: ui.borderControl }}>
        <Text style={{ fontWeight: "600", color: colors.text }}>Organize</Text>
      </Pressable>
      {summary ? <Text style={{ color: colors.muted, flexShrink: 1 }}>{summary}</Text> : null}
      <Modal visible={open} animationType="slide" onRequestClose={() => setOpen(false)}>
        <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }} keyboardShouldPersistTaps="handled">
          <Text accessibilityRole="header" style={{ fontSize: 18, fontWeight: "700", color: colors.text }}>{headline}</Text>
          <Text style={{ fontWeight: "600", color: colors.text }}>Lists</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
            {extras.collections.map((c) => chip(c.name, memberOf.includes(c.id), () => updateExtras((cur) => toggleMembership(cur, story.id, c.id))))}
          </View>
          {extras.collections.length < MAX_COLLECTIONS && (
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <TextInput value={newList} onChangeText={setNewList} maxLength={MAX_COLLECTION_NAME} placeholder="New list name" accessibilityLabel="New list name"
                placeholderTextColor={colors.muted}
                style={{ flex: 1, minHeight: 44, borderWidth: 1, borderColor: ui.borderControl, borderRadius: radius.md, paddingHorizontal: spacing.md, color: colors.text }} />
              {chip("Add list", false, () => {
                const id = `c${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
                updateExtras((cur) => {
                  const next = addCollection(cur, newList, id);
                  const created = next.collections.find((c) => c.id === id);
                  return created ? toggleMembership(next, story.id, id) : next;
                });
                setNewList("");
              })}
            </View>
          )}
          <Text style={{ fontWeight: "600", color: colors.text }}>Note (stays on this phone)</Text>
          <TextInput value={note} onChangeText={setNoteText} maxLength={MAX_NOTE_LENGTH} multiline accessibilityLabel="Note"
            placeholder="Add a note" placeholderTextColor={colors.muted}
            onBlur={() => updateExtras((cur) => setNote(cur, story.id, note))}
            style={{ minHeight: 88, borderWidth: 1, borderColor: ui.borderControl, borderRadius: radius.md, padding: spacing.md, color: colors.text, textAlignVertical: "top" }} />
          <Text style={{ fontWeight: "600", color: colors.text }}>Read later</Text>
          {reminder && <Text style={{ color: colors.muted }}>Reminder set for {new Date(reminder.at).toLocaleString()}</Text>}
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
            {REMINDER_PRESETS.map((preset) => chip(preset.label, false, () => { remind(preset.days); }))}
            {reminder && chip("Clear reminder", false, () => { clearReminder(); })}
          </View>
          {status && <Text accessibilityRole="alert" style={{ color: colors.text }}>{status}</Text>}
          {chip("Done", true, () => { updateExtras((cur) => setNote(cur, story.id, note)); setOpen(false); })}
        </ScrollView>
      </Modal>
    </View>
  );
}
