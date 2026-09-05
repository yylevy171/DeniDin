import { useEffect, useRef, useState } from "react";
import { Image, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import type { Theme } from "./theme";
import { ContextMessage, fetchMediaObjectUrl, searchClients } from "./api";

export function Button({
  label,
  onPress,
  theme,
  variant = "primary",
  disabled,
}: {
  label: string;
  onPress: () => void;
  theme: Theme;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
}) {
  const bg =
    variant === "primary" ? theme.accent : variant === "danger" ? theme.danger : "transparent";
  const color =
    variant === "ghost" ? theme.text : variant === "danger" ? "#fff" : theme.accentText;
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={{
        paddingVertical: 8,
        paddingHorizontal: 14,
        borderRadius: 8,
        backgroundColor: bg,
        borderWidth: variant === "ghost" ? 1 : 0,
        borderColor: theme.border,
        opacity: disabled ? 0.45 : 1,
      }}
    >
      <Text style={{ color, fontWeight: "600", fontSize: 14 }}>{label}</Text>
    </Pressable>
  );
}

export function Field({
  value,
  onChange,
  placeholder,
  theme,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  theme: Theme;
}) {
  return (
    <TextInput
      value={value}
      onChangeText={onChange}
      placeholder={placeholder}
      placeholderTextColor={theme.textDim}
      style={{
        borderWidth: 1,
        borderColor: theme.border,
        backgroundColor: theme.surface,
        color: theme.text,
        borderRadius: 8,
        paddingVertical: 7,
        paddingHorizontal: 10,
        minWidth: 130,
        textAlign: "right",
      }}
    />
  );
}

export function ClientNameInput({
  theme,
  value,
  onChange,
  active,
  onActivate,
}: {
  theme: Theme;
  value: string;
  onChange: (v: string) => void;
  active: boolean; // this input's dropdown is the currently-open menu
  onActivate: () => void; // ask App to make this the open menu (closes the others)
}) {
  const [suggests, setSuggests] = useState<string[]>([]);
  const [listOpen, setListOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const suppress = useRef(false);

  // external close: another menu took over, or App cleared everything
  useEffect(() => {
    if (!active) setListOpen(false);
  }, [active]);

  useEffect(() => {
    if (suppress.current) {
      suppress.current = false;
      return;
    }
    if (value.trim().length < 2) {
      setSuggests([]);
      setListOpen(false);
      return;
    }
    const h = setTimeout(() => {
      searchClients(value)
        .then((list) => {
          setSuggests(list);
          setCursor(0);
          if (list.length > 0) {
            setListOpen(true);
            onActivate();
          } else {
            setListOpen(false);
          }
        })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(h);
  }, [value]); // eslint-disable-line

  const open = active && listOpen;

  const pick = (name: string) => {
    suppress.current = true; // don't re-search the full picked name
    onChange(name);
    setSuggests([]);
    setListOpen(false);
  };

  const onKeyDown = (e: any) => {
    if (!open || suggests.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((a) => Math.min(a + 1, suggests.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(suggests[cursor]);
    } else if (e.key === "Escape") {
      setListOpen(false);
    }
  };

  return (
    <View style={{ position: "relative", zIndex: open ? 120 : 1 }}>
      {/* plain DOM input on web — gives real onKeyDown for arrow/Enter nav */}
      <input
        value={value}
        onChange={(e: any) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => {
          if (suggests.length) {
            setListOpen(true);
            onActivate();
          }
        }}
        placeholder="שם לקוח"
        dir="rtl"
        style={{
          border: `1px solid ${theme.border}`,
          background: theme.surface,
          color: theme.text,
          borderRadius: 8,
          padding: "8px 10px",
          minWidth: 150,
          fontSize: 13,
          outline: "none",
          textAlign: "right",
          fontFamily: "inherit",
        }}
      />
      {open && suggests.length ? (
        <View
          style={{
            position: "absolute",
            top: 40,
            right: 0,
            backgroundColor: theme.surface,
            borderWidth: 1,
            borderColor: theme.border,
            borderRadius: 8,
            minWidth: 200,
            maxHeight: 220,
            shadowColor: "#000",
            shadowOpacity: 0.15,
            shadowRadius: 8,
            shadowOffset: { width: 0, height: 3 },
          }}
        >
          <ScrollView>
            {suggests.map((s, i) => (
              <Pressable
                key={s}
                onPress={() => pick(s)}
                style={{
                  paddingVertical: 8,
                  paddingHorizontal: 10,
                  backgroundColor: i === active ? theme.accent : "transparent",
                }}
              >
                <Text
                  style={{
                    color: i === active ? theme.accentText : theme.text,
                    textAlign: "right",
                    fontSize: 13,
                  }}
                >
                  {s}
                </Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );
}

export function DateRange({
  theme,
  from,
  to,
  earliest,
  today,
  onFrom,
  onTo,
}: {
  theme: Theme;
  from: string;
  to: string;
  earliest: string; // absolute floor for "from"
  today: string; // absolute ceiling for "to"
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
}) {
  const inp: any = {
    border: `1px solid ${theme.border}`,
    background: theme.surface,
    color: theme.text,
    borderRadius: 8,
    padding: "7px 8px",
    fontSize: 13,
    outline: "none",
    fontFamily: "inherit",
  };
  return (
    <View style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
      {/* forceRTL reverses this row: from ends up on the right, to on the left */}
      <input
        type="date"
        value={to}
        min={from || earliest}
        max={today}
        onChange={(e: any) => onTo(e.target.value)}
        style={inp}
      />
      <Text style={{ color: theme.textDim }}>—</Text>
      <input
        type="date"
        value={from}
        min={earliest}
        max={to || today}
        onChange={(e: any) => onFrom(e.target.value)}
        style={inp}
      />
    </View>
  );
}

function OptionRow({
  label,
  on,
  bold,
  disabled,
  onPress,
  theme,
}: {
  label: string;
  on: boolean;
  bold?: boolean;
  disabled?: boolean;
  onPress: () => void;
  theme: Theme;
  key?: string;
}) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 8,
        paddingVertical: 9,
        paddingHorizontal: 10,
        opacity: disabled ? 0.38 : 1,
        backgroundColor: on ? theme.surfaceAlt : "transparent",
      }}
    >
      <Text style={{ color: on ? theme.accent : theme.textDim, fontSize: 15 }}>{on ? "☑" : "☐"}</Text>
      <Text
        style={{
          color: theme.text,
          flex: 1,
          textAlign: "right",
          fontSize: 13,
          fontWeight: bold ? "700" : "400",
        }}
      >
        {label}
      </Text>
    </Pressable>
  );
}

export function MultiSelect({
  label,
  options,
  selected,
  disabledOptions,
  onToggle,
  onSetAll,
  open,
  onToggleOpen,
  theme,
}: {
  label: string;
  options: string[];
  selected: Set<string>;
  disabledOptions?: Set<string>;
  onToggle: (o: string) => void;
  onSetAll: (on: boolean) => void;
  open: boolean;
  onToggleOpen: () => void;
  theme: Theme;
}) {
  const enabled = options.filter((o) => !disabledOptions?.has(o));
  const total = enabled.length;
  const count = enabled.filter((o) => selected.has(o)).length;
  const allOn = total > 0 && count === total;
  const summary = allOn ? "הכל" : count === 0 ? "ללא" : String(count);
  return (
    <View style={{ position: "relative", zIndex: open ? 120 : 1 }}>
      <Pressable
        onPress={onToggleOpen}
        style={{
          borderWidth: 1,
          borderColor: theme.border,
          backgroundColor: theme.surface,
          borderRadius: 8,
          paddingVertical: 8,
          paddingHorizontal: 10,
          minWidth: 150,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
        }}
      >
        <Text style={{ color: theme.text, fontSize: 13 }}>
          {label}
          {`  (${summary})`}
        </Text>
        <Text style={{ color: theme.textDim, fontSize: 11 }}>{open ? "▲" : "▼"}</Text>
      </Pressable>
      {open ? (
        <View
          style={{
            position: "absolute",
            top: 42,
            right: 0,
            backgroundColor: theme.surface,
            borderWidth: 1,
            borderColor: theme.border,
            borderRadius: 8,
            minWidth: 220,
            overflow: "hidden",
            shadowColor: "#000",
            shadowOpacity: 0.15,
            shadowRadius: 8,
            shadowOffset: { width: 0, height: 3 },
          }}
        >
          <ScrollView style={{ maxHeight: 320 }} showsVerticalScrollIndicator>
            {total === 0 ? (
              <Text style={{ color: theme.textDim, padding: 10, fontSize: 12 }}>אין ערכים</Text>
            ) : (
              <OptionRow label="הכל" on={allOn} bold onPress={() => onSetAll(!allOn)} theme={theme} />
            )}
            {options.map((o) => (
              <OptionRow
                key={o}
                label={o}
                on={selected.has(o)}
                disabled={disabledOptions?.has(o)}
                onPress={() => onToggle(o)}
                theme={theme}
              />
            ))}
          </ScrollView>
        </View>
      ) : null}
    </View>
  );
}

function ChatImage({
  path,
  theme,
  onOpen,
}: {
  path: string;
  theme: Theme;
  onOpen: (url: string) => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    let created: string | null = null;
    fetchMediaObjectUrl(path)
      .then((u) => {
        if (live) {
          created = u;
          setUrl(u);
        }
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [path]);

  if (failed)
    return <Text style={{ color: theme.textDim, fontStyle: "italic" }}>[מדיה לא זמינה]</Text>;
  if (!url) return <Text style={{ color: theme.textDim }}>…טוען תמונה</Text>;
  return (
    <Pressable onPress={() => onOpen(url)}>
      <Image
        source={{ uri: url }}
        style={{ width: 160, height: 160, borderRadius: 8, backgroundColor: theme.surfaceAlt }}
        resizeMode="cover"
      />
    </Pressable>
  );
}

export function ImageOverlay({
  url,
  onClose,
  theme,
}: {
  url: string;
  onClose: () => void;
  theme: Theme;
}) {
  return (
    <View
      style={{
        position: "absolute",
        top: 0,
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: "rgba(0,0,0,0.88)",
        alignItems: "center",
        justifyContent: "center",
        padding: 12,
        gap: 10,
        zIndex: 200,
      }}
    >
      <Image source={{ uri: url }} style={{ width: "94%", height: "86%" }} resizeMode="contain" />
      <Button label="סגירה" onPress={onClose} theme={theme} />
    </View>
  );
}

export function ChatPanel({
  messages,
  error,
  theme,
  onOpenImage,
}: {
  messages: ContextMessage[] | undefined;
  error?: string;
  theme: Theme;
  onOpenImage: (url: string) => void;
}) {
  if (error)
    return (
      <View style={{ padding: 12 }}>
        <Text style={{ color: theme.textDim, fontStyle: "italic" }}>
          השיחה שקשורה לאירוע זה אינה זמינה עוד.
        </Text>
      </View>
    );
  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 10, gap: 8 }}>
      {(messages || []).map((m) => {
        const mine = m.side === "right";
        return (
          // forceRTL is on: flex-start === right edge, flex-end === left edge
          <View key={m.message_id} style={{ alignItems: mine ? "flex-start" : "flex-end" }}>
            <View
              style={{
                maxWidth: "82%",
                backgroundColor: mine ? theme.bubbleMine : theme.bubbleTheirs,
                borderWidth: 1,
                borderColor: theme.border,
                borderRadius: 12,
                padding: 9,
                gap: 6,
              }}
            >
              {m.sender_name ? (
                <Text style={{ fontSize: 11, color: theme.textDim }}>{m.sender_name}</Text>
              ) : null}
              {m.media_url ? (
                <ChatImage path={m.media_url} theme={theme} onOpen={onOpenImage} />
              ) : null}
              {m.content ? (
                <Text style={{ color: theme.text, fontSize: 14, textAlign: "right" }}>{m.content}</Text>
              ) : null}
              {m.timestamp ? (
                <Text style={{ fontSize: 10, color: theme.textDim, textAlign: "right" }}>
                  {m.timestamp.replace("T", " ").slice(0, 16)}
                </Text>
              ) : null}
            </View>
          </View>
        );
      })}
      {(!messages || messages.length === 0) && !error ? (
        <Text style={{ color: theme.textDim }}>אין הודעות בטווח.</Text>
      ) : null}
    </ScrollView>
  );
}

const LABELS: Record<string, string> = {
  event_datetime: "תאריך אירוע",
  source_type: "סוג אירוע",
  event_subtype: "תת-סוג",
  client_name: "שם לקוח",
  payer_name: "שם משלם",
  description: "תיאור",
  amount: "סכום",
  txn_date: "תאריך תנועה",
  reference: "אסמכתא",
  reference_hint: "רמז אסמכתא",
  component_label: "תווית רכיב",
  trigger_condition: "תנאי הפעלה",
  percent: "אחוז",
  percent_base: "בסיס אחוז",
  hours: "שעות",
  hourly_rate: "תעריף שעתי",
  split_partner: "שותף לפיצול",
  split_percent: "אחוז פיצול",
  vat_status: 'סטטוס מע"מ',
  bank_number: "מספר בנק",
  bank_branch: "מספר סניף",
  bank_account: "מספר חשבון",
  accounting_document_display_number: "מספר מסמך",
  accounting_document_status_label: "סטטוס",
  accounting_document_payment_method: "אמצעי תשלום",
};
const HIDDEN = new Set([
  "event_id",
  "agreement_id",
  "component_id",
  "session_id",
  "message_id",
  "captured_at",
  "schema_version",
  "accounting_document_status",
  "accounting_document_status_code",
]);
const ALWAYS = new Set([
  "event_datetime",
  "source_type",
  "event_subtype",
  "client_name",
  "description",
  "amount",
  "txn_date",
]);

const FIELD_ORDER = [
  "event_datetime", "txn_date", "source_type", "event_subtype", "client_name", "payer_name",
  "amount", "vat_status", "description",
  "accounting_document_display_number", "accounting_document_status_label",
  "accounting_document_payment_method",
  "reference", "reference_hint", "component_label", "trigger_condition",
  "percent", "percent_base", "hours", "hourly_rate",
  "bank_number", "bank_branch", "bank_account", "split_partner", "split_percent",
];

const fmtVal = (v: any) => (v === null || v === undefined || v === "" ? "—" : String(v));

export function DetailPanel({ detail, theme }: { detail: Record<string, any> | null; theme: Theme }) {
  if (!detail) return <Text style={{ color: theme.textDim, padding: 12 }}>…טוען</Text>;
  const shown = (k: string) =>
    !HIDDEN.has(k) && (ALWAYS.has(k) || (detail[k] !== null && detail[k] !== undefined && detail[k] !== ""));
  const ordered = FIELD_ORDER.filter((k) => k in detail && shown(k));
  const extra = Object.keys(detail).filter((k) => !FIELD_ORDER.includes(k) && shown(k));
  const keys = [...ordered, ...extra];
  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ padding: 8, flexDirection: "row", flexWrap: "wrap" }}
    >
      {keys.map((k) => (
        <View key={k} style={{ width: "50%", paddingVertical: 3, paddingHorizontal: 6 }}>
          <Text style={{ fontSize: 12.5, textAlign: "right" }}>
            <Text style={{ color: theme.textDim }}>{LABELS[k] || k}: </Text>
            <Text style={{ color: theme.text, fontWeight: "600" }}>{fmtVal(detail[k])}</Text>
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
