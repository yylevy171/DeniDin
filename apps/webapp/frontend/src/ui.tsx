import { createElement, useEffect, useRef, useState } from "react";
import { Image, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import type { Theme } from "./theme";
import { ContextMessage, fetchMediaObjectUrl, searchClients } from "./api";

export function Button({
  label,
  onPress,
  theme,
  variant = "primary",
  disabled,
  iconSize,
  title,
}: {
  label: string;
  onPress: () => void;
  theme: Theme;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  iconSize?: number; // when set, renders as a square icon button at this glyph size
  title?: string; // hover tooltip (web)
}) {
  const bg =
    variant === "primary" ? theme.accent : variant === "danger" ? theme.danger : "transparent";
  const color =
    variant === "ghost" ? theme.text : variant === "danger" ? "#fff" : theme.accentText;
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      {...({ title } as any)}
      style={{
        paddingVertical: iconSize ? 6 : 8,
        paddingHorizontal: iconSize ? 10 : 14,
        borderRadius: 8,
        backgroundColor: bg,
        borderWidth: variant === "ghost" ? 1 : 0,
        borderColor: theme.border,
        opacity: disabled ? 0.45 : 1,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Text style={{ color, fontWeight: "600", fontSize: iconSize || 14, lineHeight: (iconSize || 14) + 4 }}>
        {label}
      </Text>
    </Pressable>
  );
}

// Feather-style icon paths, drawn inline as real DOM <svg> (react-native-web renders View as a
// div, so a raw SVG element nests fine on web). currentColor picks up the wrapper's `color`.
const ICON_PATHS: Record<string, string> = {
  refresh:
    '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
  gear:
    '<circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
};

/** Uniform square icon button — same box, same glyph size everywhere, soft-green fill. */
export function IconButton({
  glyph,
  icon,
  onPress,
  theme,
  title,
  disabled,
  glyphSize = 17,
}: {
  glyph?: string;
  icon?: keyof typeof ICON_PATHS; // preferred: a real inline SVG, perfectly centred
  onPress: () => void;
  theme: Theme;
  title?: string;
  disabled?: boolean;
  glyphSize?: number;
}) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      {...({ title } as any)}
      style={{
        width: 36,
        height: 36,
        borderRadius: 8,
        backgroundColor: theme.accentSoft,
        alignItems: "center",
        justifyContent: "center",
        opacity: disabled ? 0.45 : 1,
      }}
    >
      {icon ? (
        createElement("div", {
          style: { width: glyphSize, height: glyphSize, lineHeight: 0 },
          dangerouslySetInnerHTML: {
            __html: `<svg width="${glyphSize}" height="${glyphSize}" viewBox="0 0 24 24" fill="none" stroke="${theme.accentSoftText}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="display:block">${ICON_PATHS[icon]}</svg>`,
          },
        })
      ) : (
        <Text
          selectable={false}
          style={{
            color: theme.accentSoftText,
            fontSize: glyphSize,
            lineHeight: glyphSize,
            fontWeight: "700",
            ...({ display: "flex", alignItems: "center", justifyContent: "center" } as any),
          }}
        >
          {glyph}
        </Text>
      )}
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

type SearchStatus = "idle" | "searching" | "empty" | "results" | "error";

export function ClientNameInput({
  theme,
  value,
  onChange,
  menuOpen,
  onOpenMenu,
  onCloseMenu,
  onError,
}: {
  theme: Theme;
  value: string;
  onChange: (v: string) => void;
  menuOpen: boolean; // App: this input's dropdown is the currently-open menu
  onOpenMenu: () => void;
  onCloseMenu: () => void;
  onError?: (e: unknown) => void;
}) {
  const [suggests, setSuggests] = useState<string[]>([]);
  const [status, setStatus] = useState<SearchStatus>("idle");
  const [cursor, setCursor] = useState(0);
  const suppressNext = useRef(false);

  useEffect(() => {
    if (suppressNext.current) {
      suppressNext.current = false;
      return;
    }
    const q = value.trim();
    if (q.length < 2) {
      setSuggests([]);
      setStatus("idle");
      onCloseMenu();
      return;
    }
    let dead = false;
    setStatus("searching");
    onOpenMenu(); // show the "searching…" panel immediately
    const t = setTimeout(() => {
      searchClients(q)
        .then((list) => {
          if (dead) return;
          setSuggests(list);
          setCursor(0);
          setStatus(list.length ? "results" : "empty");
          onOpenMenu();
        })
        .catch((e) => {
          if (dead) return;
          setSuggests([]);
          setStatus("error");
          onOpenMenu();
          onError?.(e);
        });
    }, 250);
    return () => {
      dead = true;
      clearTimeout(t);
    };
  }, [value]); // eslint-disable-line

  const show = menuOpen && status !== "idle";

  const choose = (name: string) => {
    suppressNext.current = true; // don't re-search the picked full name
    onChange(name);
    setSuggests([]);
    onCloseMenu();
  };

  const onKeyDown = (e: any) => {
    if (!show) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, suggests.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(suggests[cursor]);
    } else if (e.key === "Escape") {
      onCloseMenu();
    }
  };

  return (
    <View style={{ position: "relative", zIndex: show ? 120 : 1 }}>
      {/* plain DOM input on web — real onKeyDown for arrow/Enter nav */}
      <input
        value={value}
        onChange={(e: any) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => {
          if (suggests.length) onOpenMenu();
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
      {show ? (
        <View
          style={{
            position: "absolute",
            top: 40,
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
          {status === "searching" ? (
            <Text style={{ color: theme.textDim, textAlign: "right", fontSize: 13, padding: 10 }}>
              מחפש…
            </Text>
          ) : status === "empty" ? (
            <Text style={{ color: theme.textDim, textAlign: "right", fontSize: 13, padding: 10 }}>
              לא נמצאו לקוחות
            </Text>
          ) : status === "error" ? (
            <Text style={{ color: theme.textDim, textAlign: "right", fontSize: 13, padding: 10 }}>
              שגיאת חיפוש
            </Text>
          ) : null}
          <ScrollView style={{ maxHeight: 260 }} showsVerticalScrollIndicator>
            {suggests.map((s, i) => (
              <Pressable
                key={s}
                onPress={() => choose(s)}
                onHoverIn={() => setCursor(i)}
                style={{
                  paddingVertical: 9,
                  paddingHorizontal: 10,
                  backgroundColor: i === cursor ? theme.accent : "transparent",
                }}
              >
                <Text
                  style={{
                    color: i === cursor ? theme.accentText : theme.text,
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
          <ScrollView style={{ maxHeight: 440 }} showsVerticalScrollIndicator>
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
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
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

const fmtVal = (v: any) => (v === null || v === undefined || v === "" ? "—" : String(v));

// The backend owns the field list, order, Hebrew labels, and include/exclude rules
// (contracts/field-manifests.md). The frontend only renders what it's given.
type DetailField = { key: string; label: string; value: any };
type Detail = {
  event_id: string;
  source_type: string | null;
  event_subtype: string | null;
  fields?: DetailField[];
  unsupported?: boolean;
  message?: string;
};

export function DetailPanel({ detail, theme }: { detail: Detail | null; theme: Theme }) {
  if (!detail) return <Text style={{ color: theme.textDim, padding: 12 }}>…טוען</Text>;
  if (detail.unsupported) {
    return (
      <Text style={{ color: theme.textDim, padding: 12, textAlign: "right" }}>
        {detail.message || "סוג אירוע לא מוכר."}
      </Text>
    );
  }
  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ padding: 8, flexDirection: "row", flexWrap: "wrap" }}
    >
      {(detail.fields || []).map((f) => (
        <View key={f.key} style={{ width: "50%", paddingVertical: 3, paddingHorizontal: 6 }}>
          <Text style={{ fontSize: 12.5, textAlign: "right" }}>
            <Text style={{ color: theme.textDim }}>{f.label}: </Text>
            <Text style={{ color: theme.text, fontWeight: "600" }}>{fmtVal(f.value)}</Text>
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}
