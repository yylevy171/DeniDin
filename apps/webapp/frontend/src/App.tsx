import { useCallback, useEffect, useMemo, useState } from "react";
import { Image, Pressable, ScrollView, Text, TextInput, View, useWindowDimensions } from "react-native";
import { THEMES, ThemeName } from "./theme";
import {
  AuthError,
  EventRow,
  fetchContext,
  fetchEventDetail,
  fetchEvents,
  getToken,
  login,
  logout,
} from "./api";
import {
  Button,
  ChatPanel,
  ClientNameInput,
  DateRange,
  DetailPanel,
  Field,
  IconButton,
  ImageOverlay,
  MultiSelect,
} from "./ui";

interface Settings {
  theme: ThemeName;
  daysBack: number;
  lookback: number;
}
const DEFAULT_SETTINGS: Settings = { theme: "light", daysBack: 7, lookback: 10 };
const SETTINGS_KEY = "denidin_ledger_settings";

// Canonical event types + subtypes (from prod data + runtime_constitution.md). The subtype
// dropdown always offers the full union; options invalid for the currently-selected type(s)
// are shown disabled rather than hidden.
const EVENT_TYPES = ["הסכם", "בנק", "חשבונית"];
const SUBTYPES_BY_TYPE: Record<string, string[]> = {
  הסכם: ["יצירה", "עדכון", "מבוטל"],
  בנק: ["הפקדה", "מבוטל"],
  חשבונית: ["חשבונית מס / קבלה", "חשבונית מס", "חשבונית זיכוי", "קבלה", "חשבון עסקה"],
};
const ALL_SUBTYPES = [
  ...new Set([
    ...SUBTYPES_BY_TYPE["הסכם"],
    ...SUBTYPES_BY_TYPE["בנק"],
    ...SUBTYPES_BY_TYPE["חשבונית"],
  ]),
];

function loadSettings(): Settings {
  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}") };
  } catch {
    return DEFAULT_SETTINGS;
  }
}
function saveSettings(s: Settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

const norm = (s: any) => String(s ?? "").toLowerCase().normalize("NFKD");

// row "date" arrives as "DD/MM/YYYY" — turn it into a sortable/comparable "YYYY-MM-DD".
function isoFromRowDate(d: string | undefined): string {
  if (!d) return "";
  const parts = d.split("/");
  if (parts.length !== 3) return "";
  const [dd, mm, yyyy] = parts;
  return `${yyyy}-${mm.padStart(2, "0")}-${dd.padStart(2, "0")}`;
}
function todayIso(): string {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
}
function isoDaysAgo(n: number): string {
  const t = new Date();
  t.setDate(t.getDate() - n);
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
}
// trailing-day count needed for the backend fetch to include the given "YYYY-MM-DD" date
function daysBackFor(iso: string): number {
  const ms = Date.now() - Date.parse(`${iso}T00:00:00`);
  if (!Number.isFinite(ms)) return 0;
  return Math.max(0, Math.ceil(ms / 86400000) + 1);
}
// absolute floor for the "from" date picker (never earlier than this)
const DATE_FLOOR = "2024-01-01";
function LoginScreen({ theme, onDone }: { theme: any; onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    setErr(null);
    const res = await login(pw);
    setBusy(false);
    if (res.ok) onDone();
    else setErr("סיסמה שגויה");
  };
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: theme.bg,
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <View
        style={{
          backgroundColor: theme.surface,
          borderRadius: 14,
          borderWidth: 1,
          borderColor: theme.border,
          padding: 24,
          gap: 14,
          width: 320,
        }}
      >
        <Text style={{ fontSize: 20, fontWeight: "700", color: theme.text, textAlign: "right" }}>
          דני-דין
        </Text>
        <Text style={{ color: theme.textDim, textAlign: "right" }}>הזינו סיסמה כדי להיכנס</Text>
        <TextInput
          value={pw}
          onChangeText={setPw}
          secureTextEntry
          placeholder="סיסמה"
          placeholderTextColor={theme.textDim}
          onSubmitEditing={submit}
          style={{
            borderWidth: 1,
            borderColor: theme.border,
            borderRadius: 8,
            padding: 10,
            color: theme.text,
            backgroundColor: theme.surfaceAlt,
            textAlign: "right",
          }}
        />
        {err ? <Text style={{ color: theme.danger, textAlign: "right" }}>{err}</Text> : null}
        <Button label={busy ? "…" : "כניסה"} onPress={submit} theme={theme} disabled={busy} />
      </View>
    </View>
  );
}

const COLUMNS: { w: number; label: string }[] = [
  { w: 18, label: "" },
  { w: 82, label: "תאריך" },
  { w: 78, label: "סוג" },
  { w: 120, label: "תת-סוג" },
  { w: 150, label: "שם לקוח" },
  { w: 100, label: "סכום" },
];

export default function App() {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const theme = THEMES[settings.theme];
  const { width } = useWindowDimensions();
  const isMobile = width < 768;

  const [rows, setRows] = useState<EventRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // draft filters — all types/subtypes selected by default (== no filter)
  const [typeSel, setTypeSel] = useState<Set<string>>(() => new Set(EVENT_TYPES));
  const [subSel, setSubSel] = useState<Set<string>>(() => new Set(ALL_SUBTYPES));
  const [clientText, setClientText] = useState("");
  const [globalText, setGlobalText] = useState("");
  const [dateFrom, setDateFrom] = useState(() => isoDaysAgo(loadSettings().daysBack));
  const [dateTo, setDateTo] = useState(() => todayIso());
  // applied filters
  const [applied, setApplied] = useState(() => ({
    type: new Set<string>(EVENT_TYPES),
    sub: new Set<string>(ALL_SUBTYPES),
    client: "",
    global: "",
    from: isoDaysAgo(loadSettings().daysBack),
    to: todayIso(),
  }));

  const [expanded, setExpanded] = useState<Record<string, { detail: any; ctx: any }>>({});
  const [sigma, setSigma] = useState<{ n: number; total: number } | null>(null);
  const [lightbox, setLightbox] = useState<{ rowId: string; url: string } | null>(null);
  const [openMenu, setOpenMenu] = useState<"type" | "sub" | "client" | null>(null);
  // sort direction — session-only (resets on reload / re-login), never persisted; default desc
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  // header toggle-all button: "expand" state shows "+" and expands all on press, then flips to
  // "collapse" ("–", collapses all on press, flips back). Its own state, not derived.
  const [allMode, setAllMode] = useState<"expand" | "collapse">("expand");
  // how many trailing days the currently-loaded `rows` actually cover (extended by a
  // date-range pick that reaches further back than settings.daysBack)
  // how many trailing days the currently-loaded `rows` cover. Starts at settings.daysBack;
  // grows ONLY when the user picks a "from" date earlier than what's loaded (nothing else).
  const [loadedDaysBack, setLoadedDaysBack] = useState<number>(() => loadSettings().daysBack);

  const onAuthErr = useCallback((e: unknown) => {
    if (e instanceof AuthError) setAuthed(false);
  }, []);

  const windowTo = useMemo(() => todayIso(), []);

  const load = useCallback(
    async (mode: "load" | "refresh") => {
      mode === "refresh" ? setRefreshing(true) : setLoading(true);
      try {
        const data = await fetchEvents(settings.daysBack);
        setRows(data.events);
        setLoadedDaysBack(settings.daysBack);
        setExpanded({});
        setSigma(null);
        setOpenMenu(null);
        setAllMode("expand");
        // reset every filter so a load / refresh / days-back change immediately shows
        // everything just fetched (otherwise a stale `applied.from` hides the new older rows)
        const from = isoDaysAgo(settings.daysBack);
        const to = todayIso();
        setDateFrom(from);
        setDateTo(to);
        setTypeSel(new Set(EVENT_TYPES));
        setSubSel(new Set(ALL_SUBTYPES));
        setClientText("");
        setGlobalText("");
        setApplied({
          type: new Set(EVENT_TYPES),
          sub: new Set(ALL_SUBTYPES),
          client: "",
          global: "",
          from,
          to,
        });
      } catch (e) {
        onAuthErr(e);
      } finally {
        setRefreshing(false);
        setLoading(false);
      }
    },
    [settings.daysBack, onAuthErr]
  );

  useEffect(() => {
    if (authed) load("load");
  }, [authed, settings.daysBack]); // eslint-disable-line

  useEffect(() => saveSettings(settings), [settings]);

  const visible = useMemo(() => {
    let out = rows.filter((r) => {
      // a fully-selected multi-select == no filter; partial (incl. empty) filters
      if (applied.type.size < EVENT_TYPES.length && !applied.type.has(r.source_type || "")) return false;
      if (applied.sub.size < ALL_SUBTYPES.length && !applied.sub.has(r.event_subtype || "")) return false;
      if (applied.client && !norm(r.client_name).includes(norm(applied.client))) return false;
      if (applied.from || applied.to) {
        const iso = isoFromRowDate(r.date);
        if (applied.from && iso && iso < applied.from) return false;
        if (applied.to && iso && iso > applied.to) return false;
      }
      if (applied.global) {
        const hay = norm(r.search_blob || Object.values(r).join(" "));
        if (!hay.includes(norm(applied.global))) return false;
      }
      return true;
    });
    out = [...out].sort((a, b) => {
      const k = (r: EventRow) => `${(r.date || "").split("/").reverse().join("")}|${r.event_id}`;
      const cmp = k(a) < k(b) ? -1 : k(a) > k(b) ? 1 : 0;
      return sortDir === "desc" ? -cmp : cmp;
    });
    return out;
  }, [rows, applied, sortDir]);

  // subtypes not reachable from any currently-selected type → shown greyed/disabled
  const disabledSubs = useMemo(() => {
    if (typeSel.size >= EVENT_TYPES.length) return new Set<string>();
    const valid = new Set<string>();
    for (const t of typeSel) for (const s of SUBTYPES_BY_TYPE[t] || []) valid.add(s);
    return new Set(ALL_SUBTYPES.filter((s) => !valid.has(s)));
  }, [typeSel]);

  // "חפש!" — client-side filtering over the loaded rows. The ONLY thing that can pull more
  // history is the user having moved "from" earlier than what's currently loaded; type/subtype/
  // client-name/free-text filters never trigger a fetch (amends Component 3.6, per 2026-09-05
  // user correction: "from" is not clamped to the window, but only the user changes it).
  const apply = async () => {
    setOpenMenu(null);
    const need = daysBackFor(dateFrom);
    if (need > loadedDaysBack) {
      setLoading(true);
      try {
        const data = await fetchEvents(need);
        setRows(data.events);
        setLoadedDaysBack(need);
      } catch (e) {
        onAuthErr(e);
        setLoading(false);
        return;
      }
      setLoading(false);
    }
    setApplied({
      type: new Set(typeSel),
      sub: new Set(subSel),
      client: clientText.trim(),
      global: globalText.trim(),
      from: dateFrom,
      to: dateTo,
    });
    setExpanded({});
    setSigma(null);
  };

  const toggleType = (t: string) => {
    const next = new Set<string>(typeSel);
    next.has(t) ? next.delete(t) : next.add(t);
    setTypeSel(next);
  };
  const toggleSub = (s: string) => {
    const next = new Set<string>(subSel);
    next.has(s) ? next.delete(s) : next.add(s);
    setSubSel(next);
  };
  const setAllTypes = (on: boolean) => setTypeSel(on ? new Set(EVENT_TYPES) : new Set());
  const setAllSubs = (on: boolean) => setSubSel(on ? new Set(ALL_SUBTYPES) : new Set());

  const toggleExpand = useCallback(
    async (id: string) => {
      setOpenMenu(null);
      if (expanded[id]) {
        const next = { ...expanded };
        delete next[id];
        setExpanded(next);
        setLightbox((lb) => (lb?.rowId === id ? null : lb));
        return;
      }
      setExpanded({ ...expanded, [id]: { detail: null, ctx: null } });
      try {
        const [detail, ctx] = await Promise.all([
          fetchEventDetail(id),
          fetchContext(id, settings.lookback),
        ]);
        setExpanded((cur) => ({ ...cur, [id]: { detail, ctx } }));
      } catch (e) {
        onAuthErr(e);
      }
    },
    [expanded, settings.lookback, onAuthErr]
  );

  const expandAll = async () => {
    setOpenMenu(null);
    const ids = visible.map((r) => r.event_id);
    // 1) open every row at once (one state update — not one-by-one, which also clobbered
    //    all-but-the-last because each toggle rebuilt from a stale `expanded`)
    setExpanded((cur) => {
      const next = { ...cur };
      for (const id of ids) if (!next[id]) next[id] = { detail: null, ctx: null };
      return next;
    });
    // 2) load content with bounded concurrency, skipping rows that already have it
    const need = ids.filter((id) => !expanded[id]?.detail);
    let i = 0;
    const worker = async () => {
      while (i < need.length) {
        const id = need[i++];
        try {
          const [detail, ctx] = await Promise.all([
            fetchEventDetail(id),
            fetchContext(id, settings.lookback),
          ]);
          setExpanded((cur) => (cur[id] ? { ...cur, [id]: { detail, ctx } } : cur));
        } catch (e) {
          onAuthErr(e);
        }
      }
    };
    await Promise.all(Array.from({ length: 6 }, worker));
  };
  const collapseAll = () => {
    setOpenMenu(null);
    setExpanded({});
    setLightbox(null);
  };
  const toggleAll = () => {
    if (allMode === "expand") {
      setAllMode("collapse"); // flip immediately — don't wait for row content to finish loading
      void expandAll();
    } else {
      collapseAll();
      setAllMode("expand");
    }
  };

  // The rendered rows — memoised so typing in an unrelated filter field (which doesn't change
  // `visible`) never rebuilds the whole (potentially multi-thousand-row) list.
  const rowList = useMemo(
    () =>
      visible.map((r) => (
        <View
          key={r.event_id}
          style={{
            backgroundColor: theme.surface,
            borderWidth: 1,
            borderColor: theme.border,
            borderRadius: 10,
          }}
        >
          <Pressable onPress={() => toggleExpand(r.event_id)} style={{ padding: 10, gap: 4 }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
              <Text style={{ color: theme.accent, fontWeight: "800", width: 18, fontSize: 16 }}>
                {expanded[r.event_id] ? "–" : "+"}
              </Text>
              <Cell w={82} text={r.date} theme={theme} />
              <Cell w={78} text={r.source_type} theme={theme} />
              <Cell w={120} text={r.event_subtype} theme={theme} />
              <Cell w={150} text={r.client_name} theme={theme} strong />
              <Cell
                w={100}
                text={r.amount != null ? `₪${r.amount.toLocaleString()}` : "—"}
                theme={theme}
              />
              <View style={{ flex: 1 }} />
            </View>
            <Text
              numberOfLines={2}
              style={{ color: theme.textDim, fontSize: 12.5, textAlign: "right", paddingHorizontal: 28 }}
            >
              {r.description || "—"}
            </Text>
          </Pressable>

          {expanded[r.event_id] ? (
            <View
              style={{
                flexDirection: isMobile ? "column" : "row",
                borderTopWidth: 1,
                borderColor: theme.border,
                height: isMobile ? undefined : 240,
              }}
            >
              <View
                style={{
                  flex: 1,
                  borderLeftWidth: isMobile ? 0 : 1,
                  borderBottomWidth: isMobile ? 1 : 0,
                  borderColor: theme.border,
                }}
              >
                <DetailPanel detail={expanded[r.event_id].detail} theme={theme} />
              </View>
              <View style={{ flex: 1, height: isMobile ? 240 : undefined }}>
                <ChatPanel
                  messages={expanded[r.event_id].ctx?.messages}
                  error={expanded[r.event_id].ctx?.error}
                  theme={theme}
                  onOpenImage={(url) => setLightbox({ rowId: r.event_id, url })}
                />
              </View>
            </View>
          ) : null}
        </View>
      )),
    [visible, expanded, theme, isMobile, toggleExpand]
  );

  const computeSigma = () => {
    setOpenMenu(null);
    const nums = visible.map((r) => r.amount).filter((a) => typeof a === "number") as number[];
    setSigma({ n: nums.length, total: nums.reduce((s, x) => s + x, 0) });
  };

  if (!authed) return <LoginScreen theme={theme} onDone={() => setAuthed(true)} />;

  return (
    <View style={{ flex: 1, backgroundColor: theme.bg }}>
      {/* top bar */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 10,
          padding: 10,
          backgroundColor: theme.surface,
          borderBottomWidth: 1,
          borderColor: theme.border,
          flexWrap: "wrap",
        }}
      >
        <Image
          source={{ uri: "/honigman-law-logo.png" }}
          style={{ width: 34, height: 40, resizeMode: "contain" }}
          accessibilityLabel="הוניגמן משרד עורכי דין"
        />
        <Text style={{ fontSize: 17, fontWeight: "800", color: theme.accent }}>דני-דין · ארועים</Text>
        <View style={{ flex: 1 }} />
        <Text style={{ color: theme.textDim, fontSize: 13 }}>
          {loading ? "…" : `${visible.length.toLocaleString()} רשומות`}
        </Text>
        <View style={{ flex: 1 }} />
        <IconButton
          icon={refreshing ? undefined : "refresh"}
          glyph={refreshing ? "…" : undefined}
          glyphSize={20}
          theme={theme}
          title="רענון"
          onPress={() => load("refresh")}
          disabled={refreshing}
        />
        <IconButton
          icon="gear"
          glyphSize={22}
          theme={theme}
          title="הגדרות"
          onPress={() => {
            setOpenMenu(null);
            setShowSettings((s) => !s);
          }}
        />
      </View>

      {showSettings ? (
        <SettingsPanel
          theme={theme}
          settings={settings}
          setSettings={setSettings}
          onClose={() => setShowSettings(false)}
          onLogout={async () => {
            await logout();
            setAuthed(false);
          }}
        />
      ) : null}

      {/* filter bar — right-to-left: dates, client, type, subtype, free text, search */}
      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          gap: 8,
          padding: 10,
          alignItems: "flex-start",
          backgroundColor: theme.surface,
          borderBottomWidth: 1,
          borderColor: theme.border,
          zIndex: 70,
        }}
      >
        <View style={{ gap: 4 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>טווח תאריכים</Text>
          <DateRange
            theme={theme}
            from={dateFrom}
            to={dateTo}
            earliest={DATE_FLOOR}
            today={windowTo}
            onFrom={setDateFrom}
            onTo={setDateTo}
          />
        </View>
        <View style={{ gap: 4 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>שם לקוח</Text>
          <ClientNameInput
            theme={theme}
            value={clientText}
            onChange={setClientText}
            menuOpen={openMenu === "client"}
            onOpenMenu={() => setOpenMenu("client")}
            onCloseMenu={() => setOpenMenu((m) => (m === "client" ? null : m))}
            onError={onAuthErr}
          />
        </View>
        <View style={{ gap: 4 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>סוג</Text>
          <MultiSelect
            label="סוג אירוע"
            options={EVENT_TYPES}
            selected={typeSel}
            onToggle={toggleType}
            onSetAll={setAllTypes}
            open={openMenu === "type"}
            onToggleOpen={() => setOpenMenu((m) => (m === "type" ? null : "type"))}
            theme={theme}
          />
        </View>
        <View style={{ gap: 4 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>תת-סוג</Text>
          <MultiSelect
            label="תת-סוג"
            options={ALL_SUBTYPES}
            selected={subSel}
            disabledOptions={disabledSubs}
            onToggle={toggleSub}
            onSetAll={setAllSubs}
            open={openMenu === "sub"}
            onToggleOpen={() => setOpenMenu((m) => (m === "sub" ? null : "sub"))}
            theme={theme}
          />
        </View>
        <View style={{ gap: 4 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>חיפוש חופשי</Text>
          <Field value={globalText} onChange={setGlobalText} placeholder="חיפוש בכל השדות" theme={theme} />
        </View>
        <View style={{ alignSelf: "flex-end", flexDirection: "row", alignItems: "center", gap: 8 }}>
          <IconButton glyph="🔍" theme={theme} title="חיפוש" onPress={apply} />
          <IconButton glyph="Σ" theme={theme} title="סיכום" onPress={computeSigma} disabled={refreshing} />
          {sigma ? (
            <Text style={{ color: theme.text, fontWeight: "700", fontSize: 13 }}>
              {sigma.n} אירועים: ₪{sigma.total.toLocaleString()}
            </Text>
          ) : null}
        </View>
      </View>

      {/* column header */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          gap: 10,
          paddingVertical: 6,
          paddingHorizontal: 20,
          backgroundColor: theme.surfaceAlt,
          borderBottomWidth: 1,
          borderColor: theme.border,
        }}
      >
        {COLUMNS.map((c, i) => {
          const isDate = c.label === "תאריך";
          if (i === 0) {
            return (
              <Pressable
                key={i}
                onPress={toggleAll}
                hitSlop={6}
                style={{ width: c.w, alignItems: "center", justifyContent: "center" }}
                {...({ title: allMode === "expand" ? "פתח הכל" : "סגור הכל" } as any)}
              >
                <Text style={{ color: theme.accent, fontSize: 18, fontWeight: "800" }}>
                  {allMode === "expand" ? "+" : "–"}
                </Text>
              </Pressable>
            );
          }
          return (
            <View
              key={i}
              style={{
                width: c.w,
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "flex-start",
                gap: 3,
              }}
            >
              <Text
                style={{ color: theme.textDim, fontSize: 11, fontWeight: "700", textAlign: "right" }}
              >
                {c.label}
              </Text>
              {isDate ? (
                <Pressable
                  onPress={() => {
                    setOpenMenu(null);
                    setSortDir((d) => (d === "desc" ? "asc" : "desc"));
                  }}
                  hitSlop={6}
                >
                  <Text style={{ color: theme.accent, fontSize: 12, fontWeight: "800" }}>
                    {sortDir === "desc" ? "▼" : "▲"}
                  </Text>
                </Pressable>
              ) : null}
            </View>
          );
        })}
        <Text style={{ flex: 1, color: theme.textDim, fontSize: 11, fontWeight: "700", textAlign: "right" }}>
          תיאור
        </Text>
      </View>

      {/* list */}
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 10, gap: 8 }}>
        {loading ? <Text style={{ color: theme.textDim }}>…טוען</Text> : null}
        {!loading && visible.length === 0 ? (
          <Text style={{ color: theme.textDim, textAlign: "center", marginTop: 30 }}>
            אין אירועים להצגה.
          </Text>
        ) : null}
        {rowList}
      </ScrollView>

      {/* click-away backdrop for open dropdowns */}
      {openMenu ? (
        <Pressable
          onPress={() => setOpenMenu(null)}
          style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, zIndex: 60 }}
        />
      ) : null}

      {/* full-app image viewer */}
      {lightbox ? (
        <ImageOverlay url={lightbox.url} theme={theme} onClose={() => setLightbox(null)} />
      ) : null}
    </View>
  );
}

function Cell({
  w,
  text,
  theme,
  strong,
  dim,
}: {
  w: number;
  text: any;
  theme: any;
  strong?: boolean;
  dim?: boolean;
}) {
  return (
    <Text
      numberOfLines={2}
      style={{
        width: w,
        color: dim ? theme.textDim : theme.text,
        fontWeight: strong ? "700" : "400",
        fontSize: 13,
        textAlign: "right",
      }}
    >
      {text == null || text === "" ? "—" : String(text)}
    </Text>
  );
}

function SettingsPanel({
  theme,
  settings,
  setSettings,
  onClose,
  onLogout,
}: {
  theme: any;
  settings: Settings;
  setSettings: (s: Settings) => void;
  onClose: () => void;
  onLogout: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const row = (label: string, control: any) => (
    <View style={{ gap: 5 }}>
      <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>{label}</Text>
      {control}
    </View>
  );

  return (
    <View style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0, zIndex: 200 }}>
      {/* backdrop — blocks the rest of the app until closed (same as the image overlay) */}
      <Pressable
        onPress={onClose}
        style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: "rgba(0,0,0,0.35)" }}
      />
      {/* small popover anchored directly under the gear (top bar is RTL-reversed, so the
          gear sits on the LEFT edge) */}
      <View
        style={{
          position: "absolute",
          top: 52,
          left: 8,
          width: 288,
          backgroundColor: theme.surface,
          borderWidth: 1,
          borderColor: theme.border,
          borderRadius: 12,
          padding: 16,
          gap: 14,
          shadowColor: "#000",
          shadowOpacity: 0.2,
          shadowRadius: 14,
          shadowOffset: { width: 0, height: 6 },
        }}
      >
        <Text style={{ color: theme.text, fontWeight: "800", fontSize: 15, textAlign: "right" }}>
          הגדרות
        </Text>

        {row(
          "ערכת נושא",
          <Button
            label={settings.theme === "light" ? "בהיר" : "כהה"}
            variant="ghost"
            theme={theme}
            onPress={() =>
              setSettings({ ...settings, theme: settings.theme === "light" ? "dark" : "light" })
            }
          />
        )}
        {row(
          "ברירת מחדל בעלייה ראשונה (ימים)",
          <MiniNum
            theme={theme}
            value={settings.daysBack}
            onChange={(n) => setSettings({ ...settings, daysBack: Math.max(1, n) })}
          />
        )}
        {row(
          "זמן סביב שיחת whatsapp (דקות)",
          <MiniNum
            theme={theme}
            value={settings.lookback}
            onChange={(n) => setSettings({ ...settings, lookback: Math.min(60, Math.max(0, n)) })}
          />
        )}

        <View style={{ height: 1, backgroundColor: theme.border, marginVertical: 2 }} />

        <Button label="שמור" theme={theme} onPress={onClose} />
        <Button label="התנתקות" variant="danger" theme={theme} onPress={onLogout} />
      </View>
    </View>
  );
}

function MiniNum({ theme, value, onChange }: { theme: any; value: number; onChange: (n: number) => void }) {
  const [t, setT] = useState(String(value));
  useEffect(() => setT(String(value)), [value]);
  const commit = (raw: string) => {
    const n = parseInt(raw, 10);
    if (Number.isFinite(n)) onChange(n);
  };
  return (
    <TextInput
      value={t}
      onChangeText={(v) => {
        setT(v);
        commit(v); // commit live — don't rely on blur (onEndEditing is unreliable on web)
      }}
      onEndEditing={() => {
        commit(t);
        setT(String(value)); // snap back to the clamped/authoritative value
      }}
      keyboardType="numeric"
      style={{
        borderWidth: 1,
        borderColor: theme.border,
        borderRadius: 6,
        paddingVertical: 5,
        paddingHorizontal: 8,
        width: 56,
        color: theme.text,
        backgroundColor: theme.surface,
        textAlign: "center",
      }}
    />
  );
}
