import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View, useWindowDimensions } from "react-native";
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
  ImageOverlay,
  MultiSelect,
} from "./ui";

interface Settings {
  theme: ThemeName;
  sort: "newest" | "oldest";
  daysBack: number;
  lookback: number;
}
const DEFAULT_SETTINGS: Settings = { theme: "light", sort: "newest", daysBack: 7, lookback: 10 };
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
// trailing-day count needed to include the given "YYYY-MM-DD" date (padded a little)
function daysBackFor(iso: string): number {
  const ms = Date.now() - Date.parse(`${iso}T00:00:00`);
  if (!Number.isFinite(ms)) return 0;
  return Math.max(0, Math.ceil(ms / 86400000) + 1);
}

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
  // how many trailing days the currently-loaded `rows` actually cover (extended by a
  // date-range pick that reaches further back than settings.daysBack)
  const [loadedDaysBack, setLoadedDaysBack] = useState<number>(() => loadSettings().daysBack);

  const onAuthErr = useCallback((e: unknown) => {
    if (e instanceof AuthError) setAuthed(false);
  }, []);

  // window bounds for the date-range picker (today-daysBack .. today)
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
        setDateFrom(isoDaysAgo(settings.daysBack));
        setDateTo(todayIso());
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
      return settings.sort === "newest" ? -cmp : cmp;
    });
    return out;
  }, [rows, applied, settings.sort]);

  // subtypes not reachable from any currently-selected type → shown greyed/disabled
  const disabledSubs = useMemo(() => {
    if (typeSel.size >= EVENT_TYPES.length) return new Set<string>();
    const valid = new Set<string>();
    for (const t of typeSel) for (const s of SUBTYPES_BY_TYPE[t] || []) valid.add(s);
    return new Set(ALL_SUBTYPES.filter((s) => !valid.has(s)));
  }, [typeSel]);

  const apply = async () => {
    setOpenMenu(null);
    // Widen the loaded window when the search reaches beyond it: an explicit "from" date, or a
    // free-text / client-name query (those are meant to search all history, not just the
    // trailing default window). The floor matches the date picker's earliest allowed date.
    const searchesAllHistory = !!globalText.trim() || !!clientText.trim();
    const want = searchesAllHistory
      ? daysBackFor("2024-01-01")
      : Math.max(settings.daysBack, dateFrom ? daysBackFor(dateFrom) : 0);
    if (want > loadedDaysBack) {
      setLoading(true);
      try {
        const data = await fetchEvents(want);
        setRows(data.events);
        setLoadedDaysBack(want);
      } catch (e) {
        onAuthErr(e);
        setLoading(false);
        return;
      }
      setLoading(false);
    }
    // an all-history search on an untouched date range should not be re-narrowed by the
    // default "from" — drop it to the floor and reflect that in the picker
    const from =
      searchesAllHistory && dateFrom === isoDaysAgo(settings.daysBack) ? "2024-01-01" : dateFrom;
    if (from !== dateFrom) setDateFrom(from);
    setApplied({
      type: new Set(typeSel),
      sub: new Set(subSel),
      client: clientText.trim(),
      global: globalText.trim(),
      from,
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

  const toggleExpand = async (id: string) => {
    setOpenMenu(null);
    if (expanded[id]) {
      const next = { ...expanded };
      delete next[id];
      setExpanded(next);
      if (lightbox?.rowId === id) setLightbox(null);
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
  };

  const expandAll = async () => {
    setOpenMenu(null);
    for (const r of visible) if (!expanded[r.event_id]) await toggleExpand(r.event_id);
  };
  const collapseAll = () => {
    setOpenMenu(null);
    setExpanded({});
    setLightbox(null);
  };

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
        <Text style={{ fontSize: 17, fontWeight: "800", color: theme.accent }}>דני-דין · ארועים</Text>
        <View style={{ flex: 1 }} />
        <Button
          label="⚙︎"
          variant="ghost"
          theme={theme}
          onPress={() => {
            setOpenMenu(null);
            setShowSettings((s) => !s);
          }}
        />
        <Button
          label={refreshing ? "…מרענן" : "רענון"}
          variant="ghost"
          theme={theme}
          onPress={() => load("refresh")}
          disabled={refreshing}
        />
        <Button label="Σ" theme={theme} onPress={computeSigma} disabled={refreshing} />
        <Button label="פתח הכל" variant="ghost" theme={theme} onPress={expandAll} />
        <Button label="סגור הכל" variant="ghost" theme={theme} onPress={collapseAll} />
      </View>

      {sigma ? (
        <View style={{ padding: 8, backgroundColor: theme.surfaceAlt }}>
          <Text style={{ color: theme.text, textAlign: "right", fontWeight: "700" }}>
            Σ ({sigma.n} אירועים): ₪{sigma.total.toLocaleString()}
          </Text>
        </View>
      ) : null}

      {showSettings ? (
        <SettingsPanel
          theme={theme}
          settings={settings}
          setSettings={setSettings}
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
            earliest="2024-01-01"
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
            active={openMenu === "client"}
            onActivate={() => setOpenMenu("client")}
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
        <View style={{ alignSelf: "flex-end" }}>
          <Button label="חפש!" theme={theme} onPress={apply} />
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
        {COLUMNS.map((c, i) => (
          <Text
            key={i}
            style={{
              width: c.w,
              color: theme.textDim,
              fontSize: 11,
              fontWeight: "700",
              textAlign: "right",
            }}
          >
            {c.label}
          </Text>
        ))}
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
        {visible.map((r) => (
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
        ))}
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
  onLogout,
}: {
  theme: any;
  settings: Settings;
  setSettings: (s: Settings) => void;
  onLogout: () => void;
}) {
  return (
    <View
      style={{
        padding: 12,
        gap: 10,
        backgroundColor: theme.surfaceAlt,
        borderBottomWidth: 1,
        borderColor: theme.border,
      }}
    >
      <View style={{ flexDirection: "row", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Text style={{ color: theme.text }}>ערכת נושא</Text>
        <Button
          label={settings.theme === "light" ? "בהיר" : "כהה"}
          variant="ghost"
          theme={theme}
          onPress={() => setSettings({ ...settings, theme: settings.theme === "light" ? "dark" : "light" })}
        />
        <Text style={{ color: theme.text }}>מיון</Text>
        <Button
          label={settings.sort === "newest" ? "חדש ראשון" : "ישן ראשון"}
          variant="ghost"
          theme={theme}
          onPress={() => setSettings({ ...settings, sort: settings.sort === "newest" ? "oldest" : "newest" })}
        />
      </View>
      <View style={{ flexDirection: "row", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Text style={{ color: theme.text }}>ברירת מחדל בעלייה ראשונה (ימים)</Text>
        <MiniNum
          theme={theme}
          value={settings.daysBack}
          onChange={(n) => setSettings({ ...settings, daysBack: Math.max(1, n) })}
        />
        <Text style={{ color: theme.text }}>זמן סביב שיחת whatsapp (דקות)</Text>
        <MiniNum
          theme={theme}
          value={settings.lookback}
          onChange={(n) => setSettings({ ...settings, lookback: Math.min(60, Math.max(0, n)) })}
        />
        <View style={{ flex: 1 }} />
        <Button label="התנתקות" variant="danger" theme={theme} onPress={onLogout} />
      </View>
    </View>
  );
}

function MiniNum({ theme, value, onChange }: { theme: any; value: number; onChange: (n: number) => void }) {
  const [t, setT] = useState(String(value));
  useEffect(() => setT(String(value)), [value]);
  return (
    <TextInput
      value={t}
      onChangeText={setT}
      onEndEditing={() => {
        const n = parseInt(t, 10);
        onChange(Number.isFinite(n) ? n : value);
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
