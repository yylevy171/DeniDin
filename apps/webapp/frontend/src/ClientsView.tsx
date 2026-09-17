import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import { Theme } from "./theme";
import { AMOUNT_STATUS_TEXT_COLOR, CLIENT_STATUS_COLORS, CLIENT_STATUS_LABELS } from "./clientsTheme";
import { AuthError, ClientRow, UnmatchedEntry, fetchClients, saveClientComment, saveClientMapping } from "./api";
import { Field, IconButton } from "./ui";

const SECTION_ORDER: ClientRow["status"][] = ["check", "active", "debt", "missing_agreement", "settled", "past"];

function fmt(n: number): string {
  return `₪${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function AmountText({ value, status, theme }: { value: number; status: "WHITE" | "YELLOW" | "GRAY"; theme: Theme }) {
  const color = AMOUNT_STATUS_TEXT_COLOR[status] ?? theme.text;
  return <Text style={{ color, fontWeight: "700", fontSize: 13 }}>{fmt(value)}</Text>;
}

function ClientRowCard({
  row,
  theme,
  onSaveComment,
}: {
  row: ClientRow;
  theme: Theme;
  onSaveComment: (clientId: string, comment: string) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
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
      <Pressable onPress={() => setExpanded((e) => !e)} style={{ padding: 10, gap: 4 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Text style={{ color: theme.accent, fontWeight: "800", width: 18, fontSize: 16 }}>
            {expanded ? "–" : "+"}
          </Text>
          <Text style={{ color: theme.text, fontWeight: "700", fontSize: 14, minWidth: 140, textAlign: "right" }}>
            {row.official_name}
          </Text>
          {row.raw_names.length ? (
            <Text style={{ color: theme.textDim, fontSize: 12 }}>({row.raw_names.join(", ")})</Text>
          ) : null}
          <View style={{ flex: 1 }} />
          <View style={{ alignItems: "flex-end" }}>
            <Text style={{ color: theme.textDim, fontSize: 11 }}>הסכם</Text>
            <AmountText value={row.display_agreed} status={row.agreed_status} theme={theme} />
          </View>
          <View style={{ alignItems: "flex-end" }}>
            <Text style={{ color: theme.textDim, fontSize: 11 }}>שולם</Text>
            <AmountText value={row.display_paid} status={row.paid_status} theme={theme} />
          </View>
        </View>
      </Pressable>

      {expanded ? (
        <View style={{ borderTopWidth: 1, borderColor: theme.border, padding: 10, gap: 10 }}>
          {row.events.length ? (
            <View style={{ gap: 4 }}>
              {row.events.map((ev, i) => (
                <View key={i} style={{ flexDirection: "row", gap: 8, flexWrap: "wrap" }}>
                  <Text style={{ color: theme.textDim, fontSize: 12, width: 100 }}>{ev.date}</Text>
                  <Text style={{ color: theme.textDim, fontSize: 12, width: 70 }}>{ev.type}</Text>
                  <Text style={{ color: theme.textDim, fontSize: 12, width: 110 }}>{ev.subtype}</Text>
                  <Text style={{ color: theme.text, fontSize: 12, flex: 1 }}>{ev.desc}</Text>
                  <Text style={{ color: theme.text, fontSize: 12, fontWeight: "700" }}>{fmt(ev.amount)}</Text>
                </View>
              ))}
            </View>
          ) : (
            <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "center" }}>לא נמצאו אירועים</Text>
          )}

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

function UnmatchedRowCard({
  row,
  theme,
  onSaveMapping,
}: {
  row: UnmatchedEntry;
  theme: Theme;
  onSaveMapping: (rawName: string, officialName: string) => Promise<void>;
}) {
  const [pick, setPick] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const submit = async (officialName: string) => {
    setSaving(true);
    try {
      await onSaveMapping(row.raw_name, officialName);
      setSaved(true);
    } finally {
      setSaving(false);
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
        gap: 6,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <Text style={{ color: theme.danger, fontWeight: "700", fontSize: 13 }}>{row.raw_name}</Text>
        <Text style={{ color: theme.textDim, fontSize: 12 }}>({row.event_count} אירועים)</Text>
        <View style={{ flex: 1 }} />
        {saved ? (
          <Text style={{ color: CLIENT_STATUS_COLORS.settled, fontSize: 12, fontWeight: "700" }}>שויך ✓</Text>
        ) : (
          <>
            <View style={{ minWidth: 160 }}>
              <Field value={pick} onChange={setPick} placeholder="שם לקוח רשמי..." theme={theme} />
            </View>
            <IconButton glyph={saving ? "…" : "🔗"} theme={theme} title="שייך" onPress={() => submit(pick)} disabled={saving || !pick.trim()} />
          </>
        )}
      </View>
      {row.suggested_matches.length ? (
        <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>
          <Text style={{ color: theme.textDim, fontSize: 11 }}>הצעות:</Text>
          {row.suggested_matches.map((s) => (
            <Pressable key={s} onPress={() => setPick(s)}>
              <Text style={{ color: theme.accent, fontSize: 11, textDecorationLine: "underline" }}>{s}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function Section({
  status,
  rows,
  theme,
  onSaveComment,
}: {
  status: ClientRow["status"];
  rows: ClientRow[];
  theme: Theme;
  onSaveComment: (clientId: string, comment: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(status === "check" || status === "debt");
  if (!rows.length) return null;
  const total = rows.reduce((s, r) => s + r.display_agreed, 0);
  return (
    <View style={{ gap: 6 }}>
      <Pressable
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
      </Pressable>
      {open ? (
        <View style={{ gap: 6 }}>
          {rows.map((r) => (
            <ClientRowCard key={r.official_name} row={r} theme={theme} onSaveComment={onSaveComment} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

export default function ClientsView({ theme, onAuthErr }: { theme: Theme; onAuthErr: (e: unknown) => void }) {
  const [clients, setClients] = useState<ClientRow[]>([]);
  const [unmatched, setUnmatched] = useState<UnmatchedEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(
    async (mode: "load" | "refresh") => {
      mode === "refresh" ? setRefreshing(true) : setLoading(true);
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

  const saveMapping = async (rawName: string, officialName: string) => {
    await saveClientMapping(rawName, officialName);
    setUnmatched((cur) => cur.filter((u) => u.raw_name !== rawName));
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
          icon={refreshing ? undefined : "refresh"}
          glyph={refreshing ? "…" : undefined}
          glyphSize={20}
          theme={theme}
          title="רענון"
          testID="clients-refresh"
          onPress={() => load("refresh")}
          disabled={refreshing}
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
              <Section key={s} status={s} rows={bySection[s] || []} theme={theme} onSaveComment={saveComment} />
            ))}

            {unmatched.length ? (
              <View style={{ gap: 8 }}>
                <Text style={{ color: theme.danger, fontWeight: "800", fontSize: 15 }}>
                  שמות לקוחות לתייג ({unmatched.length})
                </Text>
                {unmatched.map((u) => (
                  <UnmatchedRowCard key={u.raw_name} row={u} theme={theme} onSaveMapping={saveMapping} />
                ))}
              </View>
            ) : null}

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
