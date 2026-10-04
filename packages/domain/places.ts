// Generated from apps/api/app/content/places.py (ADR-043). Do not edit;
// run `python -m app.content.places > packages/domain/places.ts` in apps/api.
export type PlaceKind = "COUNTRY" | "STATE" | "DISTRICT" | "CITY";
export interface Place {
  id: string;
  country: string;
  kind: PlaceKind;
  nameEn: string;
  nameTe: string;
  parentId: string | null;
}

export const PLACE_CATALOG_VERSION = 1;
export const MAX_FOLLOWED_PLACES = 10;

export const PLACES: readonly Place[] = [
  {"id": "US", "country": "US", "kind": "COUNTRY", "nameEn": "United States", "nameTe": "అమెరికా", "parentId": null},
  {"id": "IN", "country": "IN", "kind": "COUNTRY", "nameEn": "India", "nameTe": "భారతదేశం", "parentId": null},
  {"id": "GB", "country": "GB", "kind": "COUNTRY", "nameEn": "United Kingdom", "nameTe": "యునైటెడ్ కింగ్‌డమ్", "parentId": null},
  {"id": "CA", "country": "CA", "kind": "COUNTRY", "nameEn": "Canada", "nameTe": "కెనడా", "parentId": null},
  {"id": "AU", "country": "AU", "kind": "COUNTRY", "nameEn": "Australia", "nameTe": "ఆస్ట్రేలియా", "parentId": null},
  {"id": "DE", "country": "DE", "kind": "COUNTRY", "nameEn": "Germany", "nameTe": "జర్మనీ", "parentId": null},
  {"id": "AE", "country": "AE", "kind": "COUNTRY", "nameEn": "UAE", "nameTe": "యూఏఈ", "parentId": null},
  {"id": "SG", "country": "SG", "kind": "COUNTRY", "nameEn": "Singapore", "nameTe": "సింగపూర్", "parentId": null},
  {"id": "NZ", "country": "NZ", "kind": "COUNTRY", "nameEn": "New Zealand", "nameTe": "న్యూజిలాండ్", "parentId": null},
  {"id": "IN-AP", "country": "IN", "kind": "STATE", "nameEn": "Andhra Pradesh", "nameTe": "ఆంధ్రప్రదేశ్", "parentId": "IN"},
  {"id": "IN-TG", "country": "IN", "kind": "STATE", "nameEn": "Telangana", "nameTe": "తెలంగాణ", "parentId": "IN"},
  {"id": "IN-KA", "country": "IN", "kind": "STATE", "nameEn": "Karnataka", "nameTe": "కర్ణాటక", "parentId": "IN"},
  {"id": "IN-TN", "country": "IN", "kind": "STATE", "nameEn": "Tamil Nadu", "nameTe": "తమిళనాడు", "parentId": "IN"},
  {"id": "IN-MH", "country": "IN", "kind": "STATE", "nameEn": "Maharashtra", "nameTe": "మహారాష్ట్ర", "parentId": "IN"},
  {"id": "IN-DL", "country": "IN", "kind": "STATE", "nameEn": "Delhi", "nameTe": "ఢిల్లీ", "parentId": "IN"},
  {"id": "IN-AP-visakhapatnam", "country": "IN", "kind": "DISTRICT", "nameEn": "Visakhapatnam", "nameTe": "విశాఖపట్నం", "parentId": "IN-AP"},
  {"id": "IN-AP-krishna", "country": "IN", "kind": "DISTRICT", "nameEn": "Krishna", "nameTe": "కృష్ణా", "parentId": "IN-AP"},
  {"id": "IN-AP-ntr", "country": "IN", "kind": "DISTRICT", "nameEn": "NTR (Vijayawada)", "nameTe": "ఎన్టీఆర్ (విజయవాడ)", "parentId": "IN-AP"},
  {"id": "IN-AP-guntur", "country": "IN", "kind": "DISTRICT", "nameEn": "Guntur", "nameTe": "గుంటూరు", "parentId": "IN-AP"},
  {"id": "IN-AP-tirupati", "country": "IN", "kind": "DISTRICT", "nameEn": "Tirupati", "nameTe": "తిరుపతి", "parentId": "IN-AP"},
  {"id": "IN-AP-east-godavari", "country": "IN", "kind": "DISTRICT", "nameEn": "East Godavari", "nameTe": "తూర్పు గోదావరి", "parentId": "IN-AP"},
  {"id": "IN-AP-west-godavari", "country": "IN", "kind": "DISTRICT", "nameEn": "West Godavari", "nameTe": "పశ్చిమ గోదావరి", "parentId": "IN-AP"},
  {"id": "IN-AP-nellore", "country": "IN", "kind": "DISTRICT", "nameEn": "Nellore", "nameTe": "నెల్లూరు", "parentId": "IN-AP"},
  {"id": "IN-AP-kurnool", "country": "IN", "kind": "DISTRICT", "nameEn": "Kurnool", "nameTe": "కర్నూలు", "parentId": "IN-AP"},
  {"id": "IN-AP-anantapur", "country": "IN", "kind": "DISTRICT", "nameEn": "Anantapur", "nameTe": "అనంతపురం", "parentId": "IN-AP"},
  {"id": "IN-AP-kadapa", "country": "IN", "kind": "DISTRICT", "nameEn": "Kadapa", "nameTe": "కడప", "parentId": "IN-AP"},
  {"id": "IN-AP-srikakulam", "country": "IN", "kind": "DISTRICT", "nameEn": "Srikakulam", "nameTe": "శ్రీకాకుళం", "parentId": "IN-AP"},
  {"id": "IN-AP-prakasam", "country": "IN", "kind": "DISTRICT", "nameEn": "Prakasam", "nameTe": "ప్రకాశం", "parentId": "IN-AP"},
  {"id": "IN-TG-hyderabad", "country": "IN", "kind": "DISTRICT", "nameEn": "Hyderabad", "nameTe": "హైదరాబాద్", "parentId": "IN-TG"},
  {"id": "IN-TG-rangareddy", "country": "IN", "kind": "DISTRICT", "nameEn": "Ranga Reddy", "nameTe": "రంగారెడ్డి", "parentId": "IN-TG"},
  {"id": "IN-TG-medchal", "country": "IN", "kind": "DISTRICT", "nameEn": "Medchal-Malkajgiri", "nameTe": "మేడ్చల్-మల్కాజిగిరి", "parentId": "IN-TG"},
  {"id": "IN-TG-warangal", "country": "IN", "kind": "DISTRICT", "nameEn": "Warangal", "nameTe": "వరంగల్", "parentId": "IN-TG"},
  {"id": "IN-TG-hanumakonda", "country": "IN", "kind": "DISTRICT", "nameEn": "Hanumakonda", "nameTe": "హనుమకొండ", "parentId": "IN-TG"},
  {"id": "IN-TG-karimnagar", "country": "IN", "kind": "DISTRICT", "nameEn": "Karimnagar", "nameTe": "కరీంనగర్", "parentId": "IN-TG"},
  {"id": "IN-TG-nizamabad", "country": "IN", "kind": "DISTRICT", "nameEn": "Nizamabad", "nameTe": "నిజామాబాద్", "parentId": "IN-TG"},
  {"id": "IN-TG-khammam", "country": "IN", "kind": "DISTRICT", "nameEn": "Khammam", "nameTe": "ఖమ్మం", "parentId": "IN-TG"},
  {"id": "IN-TG-nalgonda", "country": "IN", "kind": "DISTRICT", "nameEn": "Nalgonda", "nameTe": "నల్గొండ", "parentId": "IN-TG"},
  {"id": "IN-TG-mahabubnagar", "country": "IN", "kind": "DISTRICT", "nameEn": "Mahabubnagar", "nameTe": "మహబూబ్‌నగర్", "parentId": "IN-TG"},
  {"id": "IN-TG-adilabad", "country": "IN", "kind": "DISTRICT", "nameEn": "Adilabad", "nameTe": "ఆదిలాబాద్", "parentId": "IN-TG"},
  {"id": "IN-TG-medak", "country": "IN", "kind": "DISTRICT", "nameEn": "Medak", "nameTe": "మెదక్", "parentId": "IN-TG"},
  {"id": "IN-TG-sangareddy", "country": "IN", "kind": "DISTRICT", "nameEn": "Sangareddy", "nameTe": "సంగారెడ్డి", "parentId": "IN-TG"},
  {"id": "IN-KA-bengaluru", "country": "IN", "kind": "CITY", "nameEn": "Bengaluru", "nameTe": "బెంగళూరు", "parentId": "IN-KA"},
  {"id": "IN-TN-chennai", "country": "IN", "kind": "CITY", "nameEn": "Chennai", "nameTe": "చెన్నై", "parentId": "IN-TN"},
  {"id": "IN-MH-mumbai", "country": "IN", "kind": "CITY", "nameEn": "Mumbai", "nameTe": "ముంబై", "parentId": "IN-MH"},
  {"id": "IN-MH-pune", "country": "IN", "kind": "CITY", "nameEn": "Pune", "nameTe": "పుణె", "parentId": "IN-MH"},
  {"id": "US-CA", "country": "US", "kind": "STATE", "nameEn": "California", "nameTe": "కాలిఫోర్నియా", "parentId": "US"},
  {"id": "US-TX", "country": "US", "kind": "STATE", "nameEn": "Texas", "nameTe": "టెక్సాస్", "parentId": "US"},
  {"id": "US-NJ", "country": "US", "kind": "STATE", "nameEn": "New Jersey", "nameTe": "న్యూజెర్సీ", "parentId": "US"},
  {"id": "US-NY", "country": "US", "kind": "STATE", "nameEn": "New York", "nameTe": "న్యూయార్క్", "parentId": "US"},
  {"id": "US-IL", "country": "US", "kind": "STATE", "nameEn": "Illinois", "nameTe": "ఇల్లినాయిస్", "parentId": "US"},
  {"id": "US-WA", "country": "US", "kind": "STATE", "nameEn": "Washington", "nameTe": "వాషింగ్టన్", "parentId": "US"},
  {"id": "US-VA", "country": "US", "kind": "STATE", "nameEn": "Virginia", "nameTe": "వర్జీనియా", "parentId": "US"},
  {"id": "US-GA", "country": "US", "kind": "STATE", "nameEn": "Georgia", "nameTe": "జార్జియా", "parentId": "US"},
  {"id": "US-NC", "country": "US", "kind": "STATE", "nameEn": "North Carolina", "nameTe": "నార్త్ కరోలినా", "parentId": "US"},
  {"id": "US-FL", "country": "US", "kind": "STATE", "nameEn": "Florida", "nameTe": "ఫ్లోరిడా", "parentId": "US"},
  {"id": "US-MA", "country": "US", "kind": "STATE", "nameEn": "Massachusetts", "nameTe": "మసాచుసెట్స్", "parentId": "US"},
  {"id": "US-PA", "country": "US", "kind": "STATE", "nameEn": "Pennsylvania", "nameTe": "పెన్సిల్వేనియా", "parentId": "US"},
  {"id": "US-MI", "country": "US", "kind": "STATE", "nameEn": "Michigan", "nameTe": "మిషిగన్", "parentId": "US"},
  {"id": "US-OH", "country": "US", "kind": "STATE", "nameEn": "Ohio", "nameTe": "ఓహియో", "parentId": "US"},
  {"id": "US-AZ", "country": "US", "kind": "STATE", "nameEn": "Arizona", "nameTe": "అరిజోనా", "parentId": "US"},
  {"id": "US-MD", "country": "US", "kind": "STATE", "nameEn": "Maryland", "nameTe": "మేరీల్యాండ్", "parentId": "US"},
  {"id": "US-DC", "country": "US", "kind": "STATE", "nameEn": "Washington, D.C.", "nameTe": "వాషింగ్టన్ డి.సి.", "parentId": "US"},
  {"id": "US-CA-san-francisco-bay-area", "country": "US", "kind": "CITY", "nameEn": "San Francisco Bay Area", "nameTe": "శాన్ ఫ్రాన్సిస్కో బే ఏరియా", "parentId": "US-CA"},
  {"id": "US-TX-dallas", "country": "US", "kind": "CITY", "nameEn": "Dallas", "nameTe": "డాలస్", "parentId": "US-TX"},
  {"id": "US-TX-houston", "country": "US", "kind": "CITY", "nameEn": "Houston", "nameTe": "హ్యూస్టన్", "parentId": "US-TX"},
  {"id": "US-TX-austin", "country": "US", "kind": "CITY", "nameEn": "Austin", "nameTe": "ఆస్టిన్", "parentId": "US-TX"},
  {"id": "US-WA-seattle", "country": "US", "kind": "CITY", "nameEn": "Seattle", "nameTe": "సియాటిల్", "parentId": "US-WA"},
  {"id": "US-NY-new-york-city", "country": "US", "kind": "CITY", "nameEn": "New York City", "nameTe": "న్యూయార్క్ సిటీ", "parentId": "US-NY"},
  {"id": "US-NJ-edison", "country": "US", "kind": "CITY", "nameEn": "Edison", "nameTe": "ఎడిసన్", "parentId": "US-NJ"},
  {"id": "US-IL-chicago", "country": "US", "kind": "CITY", "nameEn": "Chicago", "nameTe": "చికాగో", "parentId": "US-IL"},
  {"id": "US-GA-atlanta", "country": "US", "kind": "CITY", "nameEn": "Atlanta", "nameTe": "అట్లాంటా", "parentId": "US-GA"},
  {"id": "US-NC-charlotte", "country": "US", "kind": "CITY", "nameEn": "Charlotte", "nameTe": "షార్లెట్", "parentId": "US-NC"},
];

const BY_ID = new Map(PLACES.map((place) => [place.id, place]));

export function getPlace(id: string): Place | undefined {
  return BY_ID.get(id);
}

export function placeName(id: string, language: "en" | "te"): string {
  const place = BY_ID.get(id);
  if (!place) return id;
  return language === "te" ? place.nameTe : place.nameEn;
}

// A tag plus every ancestor, for matching a story against follows.
export function expandPlaceIds(ids: readonly string[]): Set<string> {
  const out = new Set<string>();
  for (const id of ids) {
    let current = BY_ID.get(id);
    while (current) {
      out.add(current.id);
      current = current.parentId ? BY_ID.get(current.parentId) : undefined;
    }
  }
  return out;
}
