import { useCallback, useEffect, useMemo, useState } from "react";
import { NAME_COL_W, RAW_NAMES_COL_W, AMOUNT_COL_W } from "./layout";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Theme } from "./theme";
import { CLIENT_STATUS_COLORS, CLIENT_STATUS_LABELS, LINE_BUTTONS } from "./clientsTheme";
import {
  AuthError,
  ClientRow,
  LineAction,
  SuggestedMatch,
  UnmatchedEntry,
  fetchClients,
  hideUnmatched,
  saveClientComment,
  saveClientMapping,
  setClientLineStatus,
  unlinkClientMapping,
  rejectAutoMatch,
} from "./api";
import { Field, IconButton, HintPressable } from "./ui";
import AgreementsSection from "./AgreementsSection";

const SECTION_ORDER: ClientRow["status"][] = ["check", "active", "debt", "missing_agreement", "settled", "past"];

// fixed-width column layout, mirroring EventsView's COLUMNS pattern — in this RTL page the
// first column renders on the right, so keep the amount fields directly after the name instead
// of pushing them away with a trailing flex spacer (that's what made them look "left-aligned").

// unmatched-names resolution table columns (client name | resolve-to dropdown | source | comment)
const UNMATCHED_NAME_W = 140;
const UNMATCHED_PICKER_W = 220;
const UNMATCHED_COMMENT_W = 440;

function fmt(n: number): string {
  return `₪${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function AmountText({ value, theme }: { value: number; theme: Theme }) {
  const color = theme.text;
  return <Text style={{ color, fontWeight: "700", fontSize: 13 }}>{fmt(value)}</Text>;
}

/** Feature 092: the line-status buttons (לסגור / לפתוח / לבדוק / לקוח פעיל), shaded with the
 * colour of the section each one moves the line to. Gray (past) lines get none. */
function LineStatusButtons({
  row,
  onAction,
}: {
  row: ClientRow;
  onAction: (clientId: string, action: LineAction) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const buttons = LINE_BUTTONS[row.status] || [];
  if (!buttons.length) return null;
  const press = async (action: LineAction) => {
    setBusy(true);
    try {
      await onAction(row.official_name, action);
    } finally {
      setBusy(false);
    }
  };
  return (
    <View style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
      {buttons.map((b) => (
        <HintPressable
          key={b.action}
          testID={`line-btn-${b.action}-${row.official_name}`}
          {...({ title: `סימון שורת הלקוח: ${b.label}` } as any)}
          onPress={busy ? undefined : () => press(b.action)}
          disabled={busy}
          style={{
            paddingVertical: 4,
            paddingHorizontal: 10,
            borderRadius: 999,
            borderWidth: 1,
            borderColor: b.color,
            backgroundColor: `${b.color}26`,
            opacity: busy ? 0.5 : 1,
          }}
        >
          <Text style={{ color: b.color, fontSize: 12, fontWeight: "700" }}>{b.label}</Text>
        </HintPressable>
      ))}
    </View>
  );
}

function ClientRowCard({
  row,
  theme,
  onSaveComment,
  onLineAction,
  onUnlink,
  onAgreementsChanged,
  onAuthErr,
}: {
  row: ClientRow;
  theme: Theme;
  onSaveComment: (clientId: string, comment: string) => Promise<void>;
  onLineAction: (clientId: string, action: LineAction) => Promise<void>;
  onUnlink: (rawName: string, auto?: boolean) => Promise<void>;
  onAgreementsChanged: () => void;
  onAuthErr: (e: unknown) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [unlinking, setUnlinking] = useState<string | null>(null);
  // Agreement ("הסכם") events mirror the Agreements section above; this list is deposits and invoice documents only.
  const paymentEvents = row.events.filter((ev) => ev.type !== "הסכם");

  const lineAction = async (clientId: string, action: LineAction) => {
    setActionError(null);
    try {
      await onLineAction(clientId, action);
    } catch (e: any) {
      setActionError(e?.message || "עדכון הסטטוס נכשל. נסו שוב.");
    }
  };

  const unlink = async (rawName: string, auto = false) => {
    setActionError(null);
    setUnlinking(rawName);
    try {
      await onUnlink(rawName, auto);
    } catch (e: any) {
      setActionError(e?.message || "ביטול השיוך נכשל. נסו שוב.");
    } finally {
      setUnlinking(null);
    }
  };
  const [comment, setComment] = useState(row.comment);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setComment(row.comment), [row.comment]);

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSaveComment(row.official_name, comment);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch {
      setError("שמירת ההערה נכשלה. ההערה נשמרה כטיוטה — נסו שוב.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View
      testID={`client-row-${row.official_name}`}
      style={{ backgroundColor: theme.surface, borderWidth: 1, borderColor: theme.border, borderRadius: 10 }}
    >
      <HintPressable onPress={() => setExpanded((e) => !e)} style={{ padding: 10, gap: 4 }}
        {...({ title: expanded ? "סגירת פרטי הלקוח" : "פתיחת פרטי הלקוח" } as any)}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
          <Text style={{ color: theme.accent, fontWeight: "800", width: 18, fontSize: 16 }}>
            {expanded ? "–" : "+"}
          </Text>
          <Text
            numberOfLines={1}
            style={{ color: theme.text, fontWeight: "700", fontSize: 14, width: NAME_COL_W, textAlign: "right" }}
          >
            {row.official_name}
          </Text>
          <Text numberOfLines={1} style={{ color: theme.textDim, fontSize: 12, width: RAW_NAMES_COL_W }}>
            {row.raw_names.length ? `(${row.raw_names.join(", ")})` : ""}
          </Text>
          <View style={{ width: AMOUNT_COL_W, alignItems: "flex-end" }}>
            <Text style={{ color: theme.textDim, fontSize: 11 }}>הסכם</Text>
            <AmountText value={row.display_agreed} theme={theme} />
          </View>
          <View style={{ width: AMOUNT_COL_W, alignItems: "flex-end" }}>
            <Text style={{ color: theme.textDim, fontSize: 11 }}>שולם</Text>
            <AmountText value={row.display_paid} theme={theme} />
          </View>
          <LineStatusButtons row={row} onAction={lineAction} />
          <View style={{ flex: 1 }} />
        </View>
        {actionError ? <Text style={{ color: theme.danger, fontSize: 12 }}>{actionError}</Text> : null}
      </HintPressable>

      {expanded ? (
        <View style={{ borderTopWidth: 1, borderColor: theme.border, padding: 10, gap: 10 }}>
          {(
            [
              { names: row.mapped_aliases, auto: false, title: "שמות ששויכו ידנית:", hint: "בטל שיוך" },
              { names: row.auto_aliases || [], auto: true, title: "שמות ששויכו אוטומטית:", hint: "בטל שיוך אוטומטי" },
            ] as const
          ).map((group) =>
            group.names.length ? (
              <View key={group.title} style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
                <Text style={{ color: theme.textDim, fontSize: 12 }}>{group.title}</Text>
                {group.names.map((alias) => (
                  <View
                    key={alias}
                    testID={`alias-${alias}`}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      gap: 6,
                      paddingVertical: 3,
                      paddingHorizontal: 8,
                      borderRadius: 999,
                      borderWidth: 1,
                      borderColor: theme.border,
                    }}
                  >
                    <Text style={{ color: theme.text, fontSize: 12 }}>{alias}</Text>
                    <HintPressable
                      testID={`unlink-${alias}`}
                      onPress={unlinking ? undefined : () => unlink(alias, group.auto)}
                      {...({ title: group.hint } as any)}
                    >
                      <Text style={{ color: theme.danger, fontSize: 13, fontWeight: "800" }}>
                        {unlinking === alias ? "…" : "×"}
                      </Text>
                    </HintPressable>
                  </View>
                ))}
              </View>
            ) : null
          )}
          <AgreementsSection clientId={row.official_name} theme={theme} onAuthErr={onAuthErr} onTotalsChanged={onAgreementsChanged} />
          <View testID="payments-section" style={{ gap: 6 }}>
            <Text style={{ color: theme.text, fontWeight: "800", fontSize: 15, textAlign: "right" }}>תשלומים</Text>
            {paymentEvents.length ? (
              <View style={{ gap: 4, padding: 8, borderWidth: 1, borderColor: theme.border, borderRadius: 8 }}>
                {paymentEvents.map((ev, i) => (
                  <View key={i} style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
                    <Text style={{ color: theme.textDim, fontSize: 12, width: 100 }}>{ev.date}</Text>
                    <Text style={{ color: theme.textDim, fontSize: 12, width: 70 }}>{ev.type}</Text>
                    <Text style={{ color: theme.textDim, fontSize: 12, width: 110 }}>{ev.subtype}</Text>
                    <Text style={{ color: theme.text, fontSize: 12, width: 280 }}>{ev.desc}</Text>
                    <Text style={{ color: theme.text, fontSize: 12, fontWeight: "700", width: 90 }}>
                      {fmt(ev.amount)}
                    </Text>
                  </View>
                ))}
              </View>
            ) : (
              <View style={{ padding: 8, borderWidth: 1, borderColor: theme.border, borderRadius: 8 }}>
                <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "center" }}>לא נמצאו תשלומים</Text>
              </View>
            )}
          </View>

          <View style={{ gap: 6 }}>
            <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>הערות תפעוליות</Text>
            <View style={{ flexDirection: "row", gap: 8 }}>
              <View style={{ flex: 1 }}>
                <Field value={comment} onChange={setComment} placeholder="הנחיות תפעול / הערות ללקוח..." theme={theme} />
              </View>
              <IconButton
                glyph={saving ? "…" : saved ? "✓" : "💾"}
                theme={theme}
                title="שמור"
                onPress={submit}
                disabled={saving}
              />
            </View>
            {error ? <Text style={{ color: theme.danger, fontSize: 12 }}>{error}</Text> : null}
          </View>
        </View>
      ) : null}
    </View>
  );
}

const REASON_ORDER = ["דמיון בשם", "סכום זהה", "שם משפחה"];

function reasonRank(reasons: string[]): number {
  for (let i = 0; i < REASON_ORDER.length; i++) {
    if (reasons.includes(REASON_ORDER[i])) return i;
  }
  return REASON_ORDER.length;
}

/** Searchable client dropdown, ported from mapping_server.py's <select>: smart candidates
 * (same amount / name similarity / shared family name — reasons shown per option) pinned at
 * the top, then every other known official client, alphabetically. Typing filters both groups. */
function ClientPicker({
  theme,
  officialNames,
  suggestions,
  onPick,
  disabled,
  onOpenChange,
}: {
  theme: Theme;
  officialNames: string[];
  suggestions: SuggestedMatch[];
  onPick: (name: string) => void;
  disabled?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpenState] = useState(false);
  const setOpen = (v: boolean | ((o: boolean) => boolean)) => {
    setOpenState((prev) => {
      const next = typeof v === "function" ? (v as (o: boolean) => boolean)(prev) : v;
      onOpenChange?.(next);
      return next;
    });
  };

  // Feature 092: Escape closes the open dropdown without choosing anything.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setQuery("");
        setOpen(false);
      }
    };
    // capture phase: react-native-web's TextInput stops keydown propagation, so a bubbling
    // listener never sees Escape while the search field has focus.
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const suggestedNames = useMemo(() => new Set(suggestions.map((s) => s.name)), [suggestions]);
  const rest = useMemo(
    () => officialNames.filter((n) => !suggestedNames.has(n)).sort((a, b) => a.localeCompare(b, "he")),
    [officialNames, suggestedNames]
  );
  const sortedSuggestions = useMemo(
    () => [...suggestions].sort((a, b) => reasonRank(a.reasons) - reasonRank(b.reasons)),
    [suggestions]
  );

  const needle = query.trim().toLowerCase();
  const filteredSuggestions = needle
    ? sortedSuggestions.filter((s) => s.name.toLowerCase().includes(needle))
    : sortedSuggestions;
  const filteredRest = needle ? rest.filter((n) => n.toLowerCase().includes(needle)) : rest;

  const choose = (name: string) => {
    setQuery("");
    setOpen(false);
    onPick(name);
  };

  return (
    <View style={{ position: "relative", zIndex: open ? 50 : 1, width: "100%" }}>
      <View style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
        <View style={{ flex: 1 }}>
          <Field
            value={query}
            onChange={(v) => {
              setQuery(v);
              setOpen(true);
            }}
            placeholder="חפשו/בחרו לקוח רשמי לשיוך..."
            theme={theme}
            testID="unmatched-picker-input"
          />
        </View>
        <IconButton
          glyph={open ? "▴" : "▾"}
          theme={theme}
          title="הצג את כל הלקוחות"
          onPress={() => setOpen((o) => !o)}
          disabled={disabled}
        />
      </View>
      {open && !disabled ? (
        <View
          testID="unmatched-picker-list"
          style={{
            position: "absolute",
            top: 38,
            right: 0,
            left: 0,
            backgroundColor: theme.surface,
            borderWidth: 1,
            borderColor: theme.border,
            borderRadius: 8,
            maxHeight: 260,
            overflow: "hidden",
            shadowColor: "#000",
            shadowOpacity: 0.15,
            shadowRadius: 8,
            shadowOffset: { width: 0, height: 3 },
          }}
        >
          <ScrollView style={{ maxHeight: 260 }}>
            {filteredSuggestions.length ? (
              <>
                <Text style={{ color: theme.textDim, fontSize: 10, fontWeight: "700", padding: 8 }}>
                  הצעות חכמות
                </Text>
                {filteredSuggestions.map((s) => (
                  <HintPressable
                    key={s.name}
                    {...({ title: `שיוך ללקוח: ${s.name}` } as any)}
                    onPress={() => choose(s.name)}
                    style={{ paddingVertical: 8, paddingHorizontal: 10 }}
                  >
                    <Text style={{ color: theme.text, fontSize: 13, textAlign: "right" }}>{s.name}</Text>
                    {s.reasons.length ? (
                      <Text style={{ color: theme.accent, fontSize: 10, textAlign: "right" }}>
                        {s.reasons.join(" · ")}
                      </Text>
                    ) : null}
                  </HintPressable>
                ))}
              </>
            ) : null}
            {filteredRest.length ? (
              <>
                <Text style={{ color: theme.textDim, fontSize: 10, fontWeight: "700", padding: 8 }}>
                  כל הלקוחות
                </Text>
                {filteredRest.map((n) => (
                  <HintPressable key={n} {...({ title: `שיוך ללקוח: ${n}` } as any)} onPress={() => choose(n)} style={{ paddingVertical: 7, paddingHorizontal: 10 }}>
                    <Text style={{ color: theme.text, fontSize: 13, textAlign: "right" }}>{n}</Text>
                  </HintPressable>
                ))}
              </>
            ) : null}
            {!filteredSuggestions.length && !filteredRest.length ? (
              <Text style={{ color: theme.textDim, fontSize: 12, padding: 10, textAlign: "center" }}>
                לא נמצאו לקוחות תואמים
              </Text>
            ) : null}
          </ScrollView>
        </View>
      ) : null}
      {open ? (
        <HintPressable
          onPress={() => setOpen(false)}
          {...({ title: "סגירת הרשימה" } as any)}
          style={{ position: "fixed" as any, top: 0, left: 0, right: 0, bottom: 0, zIndex: -1 }}
        />
      ) : null}
    </View>
  );
}

function UnmatchedRowCard({
  row,
  theme,
  officialNames,
  onSaveMapping,
  onSaveNote,
  onHide,
}: {
  row: UnmatchedEntry;
  theme: Theme;
  officialNames: string[];
  onSaveMapping: (rawName: string, officialName: string) => Promise<void>;
  onSaveNote: (rawName: string, note: string) => Promise<void>;
  onHide: (rawName: string) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  const [hiding, setHiding] = useState(false);
  const hide = async () => {
    setHiding(true);
    try {
      await onHide(row.raw_name);
    } finally {
      setHiding(false);
    }
  };
  const [note, setNote] = useState(row.note);
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteSaved, setNoteSaved] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const resolve = async (officialName: string) => {
    setSaving(true);
    try {
      await onSaveMapping(row.raw_name, officialName);
    } finally {
      setSaving(false);
    }
  };

  const submitNote = async () => {
    setNoteSaving(true);
    try {
      await onSaveNote(row.raw_name, note);
      setNoteSaved(true);
      setTimeout(() => setNoteSaved(false), 1500);
    } finally {
      setNoteSaving(false);
    }
  };

  return (
    <View
      testID={`unmatched-row-${row.raw_name}`}
      style={{
        backgroundColor: theme.surface,
        borderWidth: 1,
        borderColor: theme.border,
        borderRadius: 10,
        padding: 10,
        gap: 8,
        flexDirection: "row",
        alignItems: "flex-start",
        position: "relative",
        // must outrank every sibling row (and the source/comment columns declared after it
        // in this same row) or its own dropdown paints underneath them once open.
        zIndex: pickerOpen ? 1000 : 1,
      }}
    >
      {/* col 1: unresolved raw name */}
      <View style={{ width: UNMATCHED_NAME_W }}>
        <Text style={{ color: theme.danger, fontWeight: "700", fontSize: 13, textAlign: "right" }}>
          {row.raw_name}
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 11, textAlign: "right" }}>
          {row.event_count ? `${row.event_count} אירועים` : "ללא אירועים"}
        </Text>
      </View>

      {/* col 2: resolve-to dropdown (full client list, smart candidates on top) */}
      <View style={{ width: UNMATCHED_PICKER_W, zIndex: 10 }}>
        <ClientPicker
          theme={theme}
          officialNames={officialNames}
          suggestions={row.suggested_matches}
          onPick={resolve}
          disabled={saving}
          onOpenChange={setPickerOpen}
        />
        {saving ? <Text style={{ color: theme.textDim, fontSize: 11 }}>משייך…</Text> : null}
      </View>

      {/* col 3: source — the actual WhatsApp/Morning/bank event line(s) with date + details,
          ported verbatim from generate_client_status.py's raw_text aggregation */}
      <View style={{ flex: 1, gap: 2 }}>
        {row.raw_text.length ? (
          row.raw_text.map((t, i) => (
            <Text key={i} style={{ color: theme.textDim, fontSize: 11, textAlign: "right" }}>
              {t}
            </Text>
          ))
        ) : (
          <Text style={{ color: theme.textDim, fontSize: 11, fontStyle: "italic", textAlign: "right" }}>
            אין פירוט מקור זמין
          </Text>
        )}
      </View>

      {/* col 4: free-text comment, saved on its own, no other action */}
      <View style={{ width: UNMATCHED_COMMENT_W, flexDirection: "row", alignItems: "center", gap: 6 }}>
        <View style={{ flex: 1 }}>
          <Field value={note} onChange={setNote} placeholder="הערה..." theme={theme} />
        </View>
        <IconButton
          glyph={noteSaving ? "…" : noteSaved ? "✓" : "💾"}
          theme={theme}
          title="שמור הערה"
          onPress={submitNote}
          disabled={noteSaving}
        />
        <HintPressable
          testID={`hide-unmatched-${row.raw_name}`}
          {...({ title: "הסרת השם מרשימת השמות לתיוג" } as any)}
          onPress={hiding ? undefined : hide}
          disabled={hiding}
          style={{
            paddingVertical: 6,
            paddingHorizontal: 10,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: theme.danger,
            opacity: hiding ? 0.5 : 1,
          }}
        >
          <Text style={{ color: theme.danger, fontSize: 12, fontWeight: "700" }}>{hiding ? "…" : "הסר מהרשימה"}</Text>
        </HintPressable>
      </View>
    </View>
  );
}

function Section({
  status,
  rows,
  theme,
  onSaveComment,
  onLineAction,
  onUnlink,
  onAgreementsChanged,
  onAuthErr,
}: {
  status: ClientRow["status"];
  rows: ClientRow[];
  theme: Theme;
  onSaveComment: (clientId: string, comment: string) => Promise<void>;
  onLineAction: (clientId: string, action: LineAction) => Promise<void>;
  onUnlink: (rawName: string, auto?: boolean) => Promise<void>;
  onAgreementsChanged: () => void;
  onAuthErr: (e: unknown) => void;
}) {
  const [open, setOpen] = useState(false);
  if (!rows.length) return null;
  const total = rows.reduce((s, r) => s + r.display_agreed, 0);
  return (
    <View testID={`section-${status}`} style={{ gap: 6 }}>
      <HintPressable
        testID={`section-header-${status}`}
        {...({ title: open ? "סגירת הקטגוריה" : "פתיחת הקטגוריה" } as any)}
        onPress={() => setOpen((o) => !o)}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 10,
          paddingVertical: 8,
          paddingHorizontal: 4,
          borderBottomWidth: 2,
          borderColor: theme.border,
        }}
      >
        <Text style={{ color: theme.textDim, fontSize: 14 }}>{open ? "–" : "+"}</Text>
        <Text style={{ color: CLIENT_STATUS_COLORS[status], fontWeight: "800", fontSize: 15 }}>
          {CLIENT_STATUS_LABELS[status]}
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 12 }}>
          {rows.length} לקוחות · {fmt(total)}
        </Text>
      </HintPressable>
      {open ? (
        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 10 }}>
            <Text style={{ width: 18 }} />
            <Text style={{ color: theme.textDim, fontSize: 11, fontWeight: "700", width: NAME_COL_W, textAlign: "right" }}>
              שם לקוח
            </Text>
            <Text style={{ color: theme.textDim, fontSize: 11, fontWeight: "700", width: RAW_NAMES_COL_W }}>
              שמות מקושרים
            </Text>
            <Text style={{ color: theme.textDim, fontSize: 11, fontWeight: "700", width: AMOUNT_COL_W, textAlign: "right" }}>
              הסכם
            </Text>
            <Text style={{ color: theme.textDim, fontSize: 11, fontWeight: "700", width: AMOUNT_COL_W, textAlign: "right" }}>
              שולם
            </Text>
          </View>
          {rows.map((r) => (
            <ClientRowCard
              key={r.official_name}
              row={r}
              theme={theme}
              onSaveComment={onSaveComment}
              onLineAction={onLineAction}
              onUnlink={onUnlink}
              onAgreementsChanged={onAgreementsChanged}
              onAuthErr={onAuthErr}
            />
          ))}
        </View>
      ) : null}
    </View>
  );
}

function UnmatchedSection({
  unmatched,
  theme,
  officialNames,
  onSaveMapping,
  onSaveNote,
  onHide,
}: {
  unmatched: UnmatchedEntry[];
  theme: Theme;
  officialNames: string[];
  onSaveMapping: (rawName: string, officialName: string) => Promise<void>;
  onSaveNote: (rawName: string, note: string) => Promise<void>;
  onHide: (rawName: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  if (!unmatched.length) return null;
  return (
    <View style={{ gap: 6 }}>
      <HintPressable
        onPress={() => setOpen((o) => !o)}
        {...({ title: open ? "סגירת הרשימה" : "פתיחת הרשימה" } as any)}
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 10,
          paddingVertical: 8,
          paddingHorizontal: 4,
          borderBottomWidth: 2,
          borderColor: theme.border,
        }}
      >
        <Text style={{ color: theme.textDim, fontSize: 14 }}>{open ? "–" : "+"}</Text>
        <Text style={{ color: theme.danger, fontWeight: "800", fontSize: 15 }}>שמות לקוחות לתייג</Text>
        <Text style={{ color: theme.textDim, fontSize: 12 }}>{unmatched.length} לתיוג</Text>
      </HintPressable>
      {open ? (
        <View
          style={{
            gap: 10,
            borderWidth: 1,
            borderColor: theme.danger,
            borderRadius: 10,
            padding: 10,
          }}
        >
          <Text style={{ color: theme.textDim, fontSize: 12 }}>
            שמות שהופיעו באירועים אך לא נמצאו ברשימת הלקוחות הרשמית ממורנינג. בחרו הצעה או הקלידו שם רשמי כדי לשייך.
          </Text>
          <View style={{ flexDirection: "row", gap: 10, paddingHorizontal: 2 }}>
            <Text style={{ width: UNMATCHED_NAME_W, color: theme.textDim, fontSize: 11, fontWeight: "700", textAlign: "right" }}>
              שם לא מזוהה
            </Text>
            <Text style={{ width: UNMATCHED_PICKER_W, color: theme.textDim, fontSize: 11, fontWeight: "700", textAlign: "right" }}>
              שיוך ללקוח
            </Text>
            <Text style={{ flex: 1, color: theme.textDim, fontSize: 11, fontWeight: "700", textAlign: "right" }}>
              מקור (תאריך ופרטי האירוע)
            </Text>
            <Text style={{ width: UNMATCHED_COMMENT_W, color: theme.textDim, fontSize: 11, fontWeight: "700", textAlign: "right" }}>
              הערה
            </Text>
          </View>
          {unmatched.map((u) => (
            <UnmatchedRowCard
              key={u.raw_name}
              row={u}
              theme={theme}
              officialNames={officialNames}
              onSaveMapping={onSaveMapping}
              onSaveNote={onSaveNote}
              onHide={onHide}
            />
          ))}
        </View>
      ) : null}
    </View>
  );
}

export default function ClientsView({
  theme,
  onAuthErr,
  refreshEpoch,
  refreshBusy,
  onRefreshAll,
}: {
  theme: Theme;
  onAuthErr: (e: unknown) => void;
  refreshEpoch: number;
  refreshBusy: boolean;
  onRefreshAll: () => void;
}) {
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [unmatched, setUnmatched] = useState<UnmatchedEntry[]>([]);
  const [loading, setLoading] = useState(true); // true from the first render: the first fetch is already pending
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(
    // "reload" = after a refresh-all (the backend already reloaded everything). "refresh" = after a
    // save: just re-read the report, which the backend recomputes from its own caches.
    async (mode: "load" | "refresh" | "reload") => {
      mode === "load" ? setLoading(true) : setRefreshing(true);
      setError(null);
      try {
        const data = await fetchClients();
        setClients(data.clients);
        setUnmatched(data.unmatched);
      } catch (e: any) {
        if (e instanceof AuthError) {
          onAuthErr(e);
        } else {
          setError(e?.message === "clients_fetch_failed"
            ? "לא ניתן לטעון את רשימת הלקוחות ממורנינג כעת. נסו שוב מאוחר יותר."
            : "שגיאה בטעינת הלקוחות.");
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [onAuthErr]
  );

  useEffect(() => {
    load("load");
  }, [load]);

  // bugfix-074: any refresh button (here or in another tab) reloads everything, then every view re-reads
  useEffect(() => {
    if (refreshEpoch > 0) load("reload");
  }, [refreshEpoch]); // eslint-disable-line

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return clients;
    return clients.filter(
      (c) =>
        c.official_name.toLowerCase().includes(needle) ||
        c.raw_names.some((r) => r.toLowerCase().includes(needle))
    );
  }, [clients, search]);

  const bySection = useMemo(() => {
    const map: Record<string, ClientRow[]> = {};
    for (const s of SECTION_ORDER) map[s] = [];
    for (const r of filtered) (map[r.status] || (map[r.status] = [])).push(r);
    return map;
  }, [filtered]);

  const saveComment = async (clientId: string, comment: string) => {
    await saveClientComment(clientId, comment);
    setClients((cur) => cur.map((c) => (c.official_name === clientId ? { ...c, comment } : c)));
  };

  const officialNames = useMemo(
    () => clients.map((c) => c.official_name).sort((a, b) => a.localeCompare(b, "he")),
    [clients]
  );

  const saveMapping = async (rawName: string, officialName: string) => {
    await saveClientMapping(rawName, officialName);
    // resolving a raw name changes that official client's raw_names/totals/events too — a
    // background full reload (not just dropping the row locally) is what makes "the relevant
    // data for that client is added to the morning client in the list" actually show up.
    setUnmatched((cur) => cur.filter((u) => u.raw_name !== rawName));
    await load("refresh");
  };

  // Feature 092: a line-status button / unlink changes routing and totals server-side, so
  // re-read the (cached, no-Morning-call) report afterwards.
  const lineAction = async (clientId: string, action: LineAction) => {
    await setClientLineStatus(clientId, action);
    await load("refresh");
  };

  const unlink = async (rawName: string, auto = false) => {
    if (auto) await rejectAutoMatch(rawName);
    else await unlinkClientMapping(rawName);
    await load("refresh");
  };

  const hide = async (rawName: string) => {
    await hideUnmatched(rawName);
    setUnmatched((cur) => cur.filter((u) => u.raw_name !== rawName));
  };

  const saveNote = async (rawName: string, note: string) => {
    await saveClientMapping(rawName, undefined, note);
    setUnmatched((cur) => cur.map((u) => (u.raw_name === rawName ? { ...u, note } : u)));
  };

  return (
    <View testID="clients-view" style={{ flex: 1, backgroundColor: theme.bg }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 10,
          padding: 10,
          backgroundColor: theme.surface,
          borderBottomWidth: 1,
          borderColor: theme.border,
        }}
      >
        <View style={{ minWidth: 220 }}>
          <Field value={search} onChange={setSearch} placeholder="חיפוש לקוח..." theme={theme} testID="clients-search" />
        </View>
        <Text testID="clients-count" style={{ color: theme.textDim, fontSize: 13 }}>
          {loading ? "…" : `${filtered.length.toLocaleString()} לקוחות`}
        </Text>
        <View style={{ flex: 1 }} />
        <IconButton
          icon={refreshing || refreshBusy ? undefined : "refresh"}
          glyph={refreshing || refreshBusy ? "…" : undefined}
          glyphSize={20}
          theme={theme}
          title="רענון"
          testID="clients-refresh"
          onPress={onRefreshAll}
          disabled={refreshing || refreshBusy}
        />
      </View>

      <ScrollView testID="clients-list" style={{ flex: 1 }} contentContainerStyle={{ padding: 10, gap: 16 }}>
        {loading ? (
          <Text testID="clients-loading" style={{ color: theme.textDim }}>
            …טוען
          </Text>
        ) : null}
        {error ? (
          <View style={{ gap: 8 }}>
            <Text testID="clients-error" style={{ color: theme.danger, textAlign: "center" }}>
              {error}
            </Text>
          </View>
        ) : null}

        {!loading && !error ? (
          <>
            {SECTION_ORDER.map((s) => (
              <Section
                key={s}
                status={s}
                rows={bySection[s] || []}
                theme={theme}
                onSaveComment={saveComment}
                onLineAction={lineAction}
                onUnlink={unlink}
                onAgreementsChanged={() => { load("refresh"); }}
                onAuthErr={onAuthErr}
              />
            ))}

            <UnmatchedSection
              unmatched={unmatched}
              theme={theme}
              officialNames={officialNames}
              onSaveMapping={saveMapping}
              onSaveNote={saveNote}
              onHide={hide}
            />

            {!filtered.length && !unmatched.length ? (
              <Text testID="clients-empty" style={{ color: theme.textDim, textAlign: "center", marginTop: 30 }}>
                אין לקוחות להצגה.
              </Text>
            ) : null}
          </>
        ) : null}
      </ScrollView>
    </View>
  );
}
