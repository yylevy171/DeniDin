// Column widths of a client row, shared so the Agreements section can line its button strip up under
// the line-status buttons ("לסגור" ...) of the client row above it.
export const NAME_COL_W = 170;
export const RAW_NAMES_COL_W = 170;
export const AMOUNT_COL_W = 92;
// Distance from the start edge of a client row's content to where its line-status buttons begin:
// "+" column (18) + name + linked names + 2 amount columns, with a 10px gap before each of the 5 items after the first.
export const LINE_BUTTONS_OFFSET = 18 + NAME_COL_W + RAW_NAMES_COL_W + 2 * AMOUNT_COL_W + 5 * 10;
