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
