// P06 / ADR-044: the pure logic lives in packages/domain so web shares it.
export {
  MAX_COLLECTIONS, MAX_COLLECTION_NAME, MAX_NOTE_LENGTH, EMPTY_EXTRAS, REMINDER_PRESETS,
  parseExtras, addCollection, deleteCollection, toggleMembership, setNote, setReminder,
  dropStory, idsInCollection, reminderTime,
} from "@teluguvarta/domain";
export type { Collection, Reminder, SavedExtras } from "@teluguvarta/domain";
