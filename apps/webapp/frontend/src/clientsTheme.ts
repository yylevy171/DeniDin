// Feature 087: the mapping tool's distinctive status TEXT colors, preserved as-is
// per the user's explicit UX direction — text/badge colors only, never backgrounds.
// The Clients tab's containers/chrome use the webapp's own theme.ts tokens; these
// constants are layered on top for status semantics only.
// Shared with the Agreements section's status chips (AgreementsSection.tsx): Active green, Completed light blue.
export const ACTIVE_GREEN = "#2f9e6e";
export const COMPLETED_LIGHT_BLUE = "#7ab8f5";
export const URGENT_PINK = "#ec4899";

export const CLIENT_STATUS_COLORS: Record<string, string> = {
  settled: COMPLETED_LIGHT_BLUE, // לקוחות סגורים - הכל שולם
  debt: "#ef4444", // לקוחות שחסר תשלומים
  missing_agreement: "#eab308", // לקוחות שחסר הסכמים
  active: ACTIVE_GREEN, // לקוחות פעילים
  check: URGENT_PINK, // לטיפול מיידי
  past: "#888888", // לקוחות עבר (no accent — dim/neutral)
};

export const CLIENT_STATUS_LABELS: Record<string, string> = {
  settled: "סגור - שולם",
  debt: "חוב פתוח",
  missing_agreement: "חסר הסכם",
  active: "לקוח פעיל",
  check: "לטיפול מיידי",
  past: "לקוח עבר",
};

// Feature 092: line-status buttons. Each is shaded with the colour of the section it moves the
// line to (לפתוח uses the neutral gray). Which buttons a line shows depends on its section;
// gray (past) lines get none.
export type LineButton = { action: "close" | "reopen" | "check" | "active"; label: string; color: string };
const BTN_CLOSE: LineButton = { action: "close", label: "לסגור", color: CLIENT_STATUS_COLORS.settled };
const BTN_REOPEN: LineButton = { action: "reopen", label: "לפתוח", color: CLIENT_STATUS_COLORS.past };
const BTN_CHECK: LineButton = { action: "check", label: "לטיפול מיידי", color: CLIENT_STATUS_COLORS.check };
const BTN_ACTIVE: LineButton = { action: "active", label: "לקוח פעיל", color: CLIENT_STATUS_COLORS.active };

export const LINE_BUTTONS: Record<string, LineButton[]> = {
  check: [BTN_CLOSE, BTN_ACTIVE],
  active: [BTN_CLOSE, BTN_CHECK],
  debt: [BTN_CLOSE, BTN_CHECK, BTN_ACTIVE],
  missing_agreement: [BTN_CLOSE, BTN_CHECK, BTN_ACTIVE],
  settled: [BTN_REOPEN, BTN_CHECK, BTN_ACTIVE],
  past: [],
};
