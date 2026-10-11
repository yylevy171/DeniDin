// Feature 087: the mapping tool's distinctive status TEXT colors, preserved as-is
// per the user's explicit UX direction — text/badge colors only, never backgrounds.
// The Clients tab's containers/chrome use the webapp's own theme.ts tokens; these
// constants are layered on top for status semantics only.
export const CLIENT_STATUS_COLORS: Record<string, string> = {
  settled: "#10b981", // לקוחות סגורים - הכל שולם
  debt: "#ef4444", // לקוחות שחסר תשלומים
  missing_agreement: "#eab308", // לקוחות שחסר הסכמים
  active: "#38bdf8", // לקוחות פעילים
  check: "#3b82f6", // לבדוק!
  past: "#888888", // לקוחות עבר (no accent — dim/neutral)
};

export const CLIENT_STATUS_LABELS: Record<string, string> = {
  settled: "סגור - שולם",
  debt: "חוב פתוח",
  missing_agreement: "חסר הסכם",
  active: "לקוח פעיל",
  check: "לבדוק",
  past: "לקוח עבר",
};

// amount-field text colors (agreed_status / paid_status), from mapping_server.py
export const AMOUNT_STATUS_TEXT_COLOR: Record<string, string | undefined> = {
  YELLOW: "#eab308", // inferred / uncertain
  GRAY: "#888888", // overridden by an explicit close/settle directive
  WHITE: undefined, // no override — inherit the surrounding theme text color
};

// Feature 092: line-status buttons. Each is shaded with the colour of the section it moves the
// line to (לפתוח uses the neutral gray). Which buttons a line shows depends on its section;
// gray (past) lines get none.
export type LineButton = { action: "close" | "reopen" | "check" | "active"; label: string; color: string };
const BTN_CLOSE: LineButton = { action: "close", label: "לסגור", color: CLIENT_STATUS_COLORS.settled };
const BTN_REOPEN: LineButton = { action: "reopen", label: "לפתוח", color: CLIENT_STATUS_COLORS.past };
const BTN_CHECK: LineButton = { action: "check", label: "לבדוק", color: CLIENT_STATUS_COLORS.check };
const BTN_ACTIVE: LineButton = { action: "active", label: "לקוח פעיל", color: CLIENT_STATUS_COLORS.active };

export const LINE_BUTTONS: Record<string, LineButton[]> = {
  check: [BTN_CLOSE, BTN_ACTIVE],
  active: [BTN_CLOSE, BTN_CHECK],
  debt: [BTN_CLOSE, BTN_CHECK, BTN_ACTIVE],
  missing_agreement: [BTN_CLOSE, BTN_CHECK, BTN_ACTIVE],
  settled: [BTN_REOPEN, BTN_CHECK, BTN_ACTIVE],
  past: [],
};
