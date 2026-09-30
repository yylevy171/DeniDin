import { useCallback, useEffect, useState } from "react";
import { Image, Pressable, Text, TextInput, View } from "react-native";
import { THEMES, ThemeName } from "./theme";
import { AuthError, getToken, login, logout } from "./api";
import { Button, IconButton } from "./ui";
import EventsView from "./EventsView";
import ClientsView from "./ClientsView";

type Tab = "events" | "clients";

interface Settings {
  theme: ThemeName;
  daysBack: number;
  lookback: number;
}
const DEFAULT_SETTINGS: Settings = { theme: "light", daysBack: 7, lookback: 10 };
const SETTINGS_KEY = "denidin_ledger_settings";
const TAB_KEY = "denidin_active_tab";

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
function loadTab(): Tab {
  try {
    const t = localStorage.getItem(TAB_KEY);
    return t === "clients" ? "clients" : "events";
  } catch {
    return "events";
  }
}
function saveTab(t: Tab) {
  try {
    localStorage.setItem(TAB_KEY, t);
  } catch {
    /* ignore */
  }
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
      testID="login-screen"
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
          testID="password-input"
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
        {err ? (
          <Text testID="login-error" style={{ color: theme.danger, textAlign: "right" }}>
            {err}
          </Text>
        ) : null}
        <Button
          label={busy ? "…" : "כניסה"}
          onPress={submit}
          theme={theme}
          disabled={busy}
          testID="login-submit"
        />
      </View>
    </View>
  );
}

function TabButton({
  label,
  active,
  onPress,
  theme,
  testID,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  theme: any;
  testID?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      testID={testID}
      style={{
        paddingVertical: 6,
        paddingHorizontal: 14,
        borderRadius: 8,
        backgroundColor: active ? theme.accentSoft : "transparent",
      }}
    >
      <Text
        style={{
          color: active ? theme.accentSoftText : theme.textDim,
          fontWeight: active ? "800" : "600",
          fontSize: 14,
        }}
      >
        {label}
      </Text>
    </Pressable>
  );
}

export default function App() {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [activeTab, setActiveTab] = useState<Tab>(loadTab);
  const [showSettings, setShowSettings] = useState(false);
  // A tab is mounted the first time it's opened and then kept mounted (just hidden), so
  // switching tabs never refetches - data reloads only on page refresh or a refresh button.
  const [visited, setVisited] = useState<Set<Tab>>(() => new Set([loadTab()]));
  const theme = THEMES[settings.theme];

  // Stable identity: the views list this in their load-callback deps, so a new function on every
  // App render would re-run their fetch effects on each tab switch.
  const onAuthErr = useCallback((e: unknown) => {
    if (e instanceof AuthError) setAuthed(false);
  }, []);

  useEffect(() => saveSettings(settings), [settings]);
  useEffect(() => saveTab(activeTab), [activeTab]);
  useEffect(() => {
    setVisited((v) => (v.has(activeTab) ? v : new Set(v).add(activeTab)));
  }, [activeTab]);

  // expose the active theme as an html attribute so acceptance tests (and any future CSS)
  // can read it without inspecting computed colours
  useEffect(() => {
    try {
      document.documentElement.setAttribute("data-theme", settings.theme);
    } catch {
      /* non-browser render */
    }
  }, [settings.theme]);

  if (!authed) return <LoginScreen theme={theme} onDone={() => setAuthed(true)} />;

  return (
    <View testID="app-ready" style={{ flex: 1, backgroundColor: theme.bg }}>
      {/* shared top bar: logo, tabs, settings gear */}
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
          testID="logo"
          source={{ uri: "/honigman-law-logo.png" }}
          style={{ width: 34, height: 40, resizeMode: "contain" }}
          accessibilityLabel="הוניגמן משרד עורכי דין"
        />
        <Text style={{ fontSize: 17, fontWeight: "800", color: theme.accent }}>דני-דין</Text>
        <View style={{ flexDirection: "row", gap: 4, marginRight: 8 }}>
          <TabButton
            label="ארועים"
            active={activeTab === "events"}
            onPress={() => setActiveTab("events")}
            theme={theme}
            testID="tab-events"
          />
          <TabButton
            label="לקוחות"
            active={activeTab === "clients"}
            onPress={() => setActiveTab("clients")}
            theme={theme}
            testID="tab-clients"
          />
        </View>
        <View style={{ flex: 1 }} />
        <IconButton
          icon="gear"
          glyphSize={22}
          theme={theme}
          title="הגדרות"
          testID="settings-gear"
          onPress={() => setShowSettings((s) => !s)}
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

      {visited.has("events") ? (
        <View style={{ flex: 1, display: activeTab === "events" ? "flex" : "none" }}>
          <EventsView theme={theme} settings={settings} onAuthErr={onAuthErr} />
        </View>
      ) : null}
      {visited.has("clients") ? (
        <View style={{ flex: 1, display: activeTab === "clients" ? "flex" : "none" }}>
          <ClientsView theme={theme} onAuthErr={onAuthErr} />
        </View>
      ) : null}
    </View>
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
    <View testID="settings-panel" style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0, zIndex: 200 }}>
      <Pressable
        testID="settings-backdrop"
        onPress={onClose}
        style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: "rgba(0,0,0,0.35)" }}
      />
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
            testID="setting-theme"
            onPress={() =>
              setSettings({ ...settings, theme: settings.theme === "light" ? "dark" : "light" })
            }
          />
        )}
        {row(
          "ברירת מחדל בעלייה ראשונה (ימים)",
          <MiniNum
            theme={theme}
            testID="setting-days-back"
            value={settings.daysBack}
            onChange={(n) => setSettings({ ...settings, daysBack: Math.max(1, n) })}
          />
        )}
        {row(
          "זמן סביב שיחת whatsapp (דקות)",
          <MiniNum
            theme={theme}
            testID="setting-lookback"
            value={settings.lookback}
            onChange={(n) => setSettings({ ...settings, lookback: Math.min(60, Math.max(0, n)) })}
          />
        )}

        <View style={{ height: 1, backgroundColor: theme.border, marginVertical: 2 }} />

        <Button label="שמור" theme={theme} onPress={onClose} testID="settings-close" />
        <Button label="התנתקות" variant="danger" theme={theme} onPress={onLogout} testID="setting-logout" />
      </View>
    </View>
  );
}

function MiniNum({
  theme,
  value,
  onChange,
  testID,
}: {
  theme: any;
  value: number;
  onChange: (n: number) => void;
  testID?: string;
}) {
  const [t, setT] = useState(String(value));
  useEffect(() => setT(String(value)), [value]);
  const commit = (raw: string) => {
    const n = parseInt(raw, 10);
    if (Number.isFinite(n)) onChange(n);
  };
  return (
    <TextInput
      testID={testID}
      value={t}
      onChangeText={(v) => {
        setT(v);
        commit(v);
      }}
      onEndEditing={() => {
        commit(t);
        setT(String(value));
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
