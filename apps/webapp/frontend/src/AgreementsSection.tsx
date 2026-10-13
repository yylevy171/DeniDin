// Feature 089: the "הסכמים" section of an expanded client row - list, edit, lifecycle, history.
// Every write goes through the webapp backend to the Agreements DB; the screen always shows the
// state the server returned (and the server's `locked` flag), never a locally guessed one.
import React, { useCallback, useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { Theme } from "./theme";
import {
  Agreement,
  AgreementComponent,
  AgreementsApiError,
  AuthError,
  addComponent,
  createAgreement,
  deleteComponent,
  editAgreement,
  editComponent,
  fetchClientAgreements,
  setAgreementStatus,
  setComponentStatus,
} from "./api";
import { Button, Field, IconButton } from "./ui";

// One status vocabulary for agreements and components (human decision 2026-10-13):
// Pending = gray "לא פעיל", Active = green "פעיל", Completed = light blue "סגור", Cancelled = light red "מבוטל".
const STATUS_LABEL: Record<string, string> = { Pending: "לא פעיל", Active: "פעיל", Completed: "סגור", Cancelled: "מבוטל" };
const AGREEMENT_STATUS_LABEL = STATUS_LABEL;
const COMPONENT_STATUS_LABEL = STATUS_LABEL;
function statusColors(theme: Theme, status: string): { color: string; background: string } {
  const dark = theme.name === "dark";
  switch (status) {
    case "Active": return { color: "#ffffff", background: dark ? "#2f8f68" : "#1c7c54" };
    case "Completed": return dark ? { color: "#8ab8ff", background: "#1f3556" } : { color: "#2563b8", background: "#dbeafe" };
    case "Cancelled": return dark ? { color: "#ff9b9b", background: "#4a2626" } : { color: "#b23b3b", background: "#fde2e2" };
    default: return dark ? { color: "#d0d8d4", background: "#3a4440" } : { color: "#4a5651", background: "#e3e6e5" };
  }
}
// Icon-button colours (Feature 089 UI decision, 2026-10-13). The glyph colour says what the button does
// (edit black, complete dark green, cancel red, add blue, trash gray); the fill says whose row it is:
// agreement buttons use IconButton's default soft green, component buttons a light blue.
type Tone = { color?: string; background?: string };
type Role = "edit" | "complete" | "cancel" | "add" | "trash";
function glyph(theme: Theme, role: Role): string {
  const dark = theme.name === "dark";
  switch (role) {
    case "edit": return dark ? "#ffffff" : "#000000";
    case "complete": return dark ? "#5fd99a" : "#0b4d31";
    case "cancel": return dark ? "#ff8a8a" : "#c62828";
    case "add": return dark ? "#8ab8ff" : "#2563b8";
    default: return dark ? "#aab3ae" : "#6b7280";
  }
}
function tone(theme: Theme, role: Role, onComponent: boolean): Tone {
  const dark = theme.name === "dark";
  const background = onComponent ? (dark ? "#1f3556" : "#dbeafe") : undefined;
  return { color: glyph(theme, role), background };
}
const NEW_AGREEMENT_TONE = (theme: Theme): Tone =>
  theme.name === "dark" ? { color: "#ffffff", background: "#3a4440" } : { color: "#000000", background: "#e1e4e3" };

// Fixed-width button strip shared by agreement and component rows so the buttons line up:
// [edit] gap [complete|activate|reopen] [cancel] gap [add|trash]; an unavailable button keeps its slot.
const SLOT = 36;
function Slot({ children }: { children?: React.ReactNode }) {
  return <View style={{ width: SLOT, height: SLOT }}>{children}</View>;
}
function Strip({ edit, mid, cancel, last }: {
  edit: React.ReactNode; mid: React.ReactNode; cancel: React.ReactNode; last: React.ReactNode;
}) {
  return (
    <View style={{ flexDirection: "row", gap: 4, alignItems: "center" }}>
      <Slot>{edit}</Slot>
      <View style={{ width: 14 }} />
      <Slot>{mid}</Slot>
      <Slot>{cancel}</Slot>
      <View style={{ width: 14 }} />
      <Slot>{last}</Slot>
    </View>
  );
}
const VAT_CHOICES = ["כולל", "לא כולל", "לא צוין"];
const BUSY_MESSAGE = "יומן האירועים עמוס כרגע. נסו שוב בעוד דקה.";

type ComponentDraft = {
  label: string; description: string; amount: string; percent: string; percent_base: string;
  trigger_condition: string; vat_status: string;
};
const EMPTY_COMPONENT: ComponentDraft = {
  label: "", description: "", amount: "", percent: "", percent_base: "", trigger_condition: "",
  vat_status: "לא צוין",
};
const COMPONENT_FIELDS: Array<[keyof ComponentDraft, string]> = [
  ["label", "שם הרכיב"], ["description", "תיאור (ניסוח)"], ["amount", "סכום"], ["percent", "אחוז"],
  ["percent_base", "בסיס האחוז"], ["trigger_condition", "תנאי"],
];

/** The stored VAT value mapped onto one of the three radio choices ("לא צוין" when nothing usable is stored). */
function vatChoice(raw: string | null | undefined): string {
  const v = (raw || "").trim();
  if (v.startsWith("לא כולל")) return "לא כולל";
  if (v.startsWith("כולל")) return "כולל";
  return "לא צוין";
}

function draftOf(c: AgreementComponent): ComponentDraft {
  const text = (v: unknown) => (v === null || v === undefined ? "" : String(v));
  return {
    label: c.label, description: text(c.description), amount: text(c.amount), percent: text(c.percent),
    percent_base: text(c.percent_base), trigger_condition: text(c.trigger_condition),
    vat_status: vatChoice(c.vat_status),
  };
}

function payloadOf(d: ComponentDraft): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  (Object.keys(d) as Array<keyof ComponentDraft>).forEach((k) => {
    out[k] = d[k].trim() === "" ? null : d[k].trim();
  });
  return out;
}

function describeError(e: unknown): string {
  if (e instanceof AgreementsApiError) {
    if (e.code === "ledger_busy") return BUSY_MESSAGE;
    const fields = Object.entries(e.fields).map(([k, v]) => `${k}: ${v}`).join("; ");
    return fields ? `${e.message} (${fields})` : e.message;
  }
  return "הפעולה נכשלה. נסו שוב.";
}

function amountText(c: AgreementComponent): string {
  const parts: string[] = [];
  if (c.amount !== null && c.amount !== undefined) parts.push(`₪${c.amount.toLocaleString()}`);
  if (c.percent !== null && c.percent !== undefined) parts.push(`${c.percent}%${c.percent_base ? ` ${c.percent_base}` : ""}`);
  return parts.join(" + ");
}

/** The VAT column: "included" / "not included" / "unspecified" (nothing stored). */
export function vatText(c: AgreementComponent): string {
  const raw = (c.vat_status || "").trim();
  if (!raw || raw === "לא צוין") return "מע״מ: לא צוין";
  if (raw.startsWith("לא כולל")) return "לא כולל מע״מ";
  if (raw.startsWith("כולל")) return "כולל מע״מ";
  return `מע״מ: ${raw}`;
}

function StatusBadge({ status, label, testID, theme }: { status: string; label: string; testID: string; theme: Theme }) {
  const { color, background } = statusColors(theme, status);
  return (
    <View style={{ backgroundColor: background, borderRadius: 6, paddingVertical: 2, paddingHorizontal: 10, width: 64, alignItems: "center" }}>
      <Text testID={testID} style={{ color, fontWeight: "700", fontSize: 12 }}>
        {label}
      </Text>
    </View>
  );
}

function RadioGroup({ label, choices, value, onChange, theme, testPrefix }: {
  label: string; choices: string[]; value: string; onChange: (v: string) => void; theme: Theme; testPrefix: string;
}) {
  return (
    <View style={{ flexDirection: "row", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
      <Text style={{ color: theme.textDim, fontSize: 12 }}>{label}</Text>
      {choices.map((v) => {
        const on = value === v;
        return (
          <Pressable key={v} testID={`${testPrefix}-${v}`} onPress={() => onChange(v)} accessibilityRole="radio"
                     accessibilityState={{ checked: on }}
                     style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
            <View style={{ width: 16, height: 16, borderRadius: 8, borderWidth: 2, borderColor: on ? theme.accent : theme.border,
                           alignItems: "center", justifyContent: "center" }}>
              {on ? <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: theme.accent }} /> : null}
            </View>
            <Text style={{ color: theme.text, fontSize: 13 }}>{v}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function ComponentForm({
  title, initial, theme, onSave, onCancel, testPrefix,
}: {
  title: string; initial: ComponentDraft; theme: Theme; testPrefix: string;
  onSave: (draft: ComponentDraft) => Promise<void>; onCancel: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    if (!draft.label.trim()) return setError("יש להזין שם לרכיב.");
    if (!draft.amount.trim() && !draft.percent.trim()) return setError("יש להזין סכום או אחוז.");
    setSaving(true);
    setError(null);
    try {
      await onSave(draft);
    } catch (e) {
      if (e instanceof AuthError) throw e;
      setError(describeError(e));
    } finally {
      setSaving(false);
    }
  };
  return (
    <View testID={`${testPrefix}-form`} style={{ gap: 6, padding: 8, borderWidth: 1, borderColor: theme.border, borderRadius: 8 }}>
      <Text style={{ color: theme.text, fontWeight: "700", textAlign: "right" }}>{title}</Text>
      {COMPONENT_FIELDS.map(([key, label]) => (
        <View key={key} style={{ gap: 2 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>{label}</Text>
          <Field value={draft[key]} onChange={(v) => setDraft({ ...draft, [key]: v })} placeholder={label} theme={theme}
                 testID={`${testPrefix}-${key}`} />
        </View>
      ))}
      <RadioGroup label="מע״מ:" choices={VAT_CHOICES} value={draft.vat_status} theme={theme}
                  testPrefix={`${testPrefix}-vat`} onChange={(v) => setDraft({ ...draft, vat_status: v })} />
      {error ? <Text testID={`${testPrefix}-error`} style={{ color: theme.danger, fontSize: 12 }}>{error}</Text> : null}
      <View style={{ flexDirection: "row", gap: 8 }}>
        <Button label={saving ? "…" : "שמור"} theme={theme} testID={`${testPrefix}-save`} onPress={submit} disabled={saving} />
        <Button label="ביטול" theme={theme} variant="ghost" testID={`${testPrefix}-cancel`} onPress={onCancel} />
      </View>
    </View>
  );
}

function AgreementForm({
  theme, clientId, agreement, onSaved, onCancel,
}: {
  theme: Theme; clientId: string; agreement: Agreement | null;
  onSaved: () => Promise<void>; onCancel: () => void;
}) {
  const [title, setTitle] = useState(agreement?.title ?? "");
  const [publicId, setPublicId] = useState(agreement?.agreement_id ?? "");
  const [payer, setPayer] = useState(agreement?.payer_name ?? "");
  const [partner, setPartner] = useState(agreement?.partner_name ?? "");
  const [percent, setPercent] = useState(agreement?.partner_percent != null ? String(agreement.partner_percent) : "");
  const [component, setComponent] = useState<ComponentDraft>(EMPTY_COMPONENT);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const blank = (v: string) => (v.trim() === "" ? null : v.trim());
  const submit = async () => {
    setError(null);
    if (!agreement) {
      if (!title.trim()) return setError("יש להזין שם להסכם.");
      if (!component.label.trim() || (!component.amount.trim() && !component.percent.trim())) {
        return setError("יש להגדיר לפחות רכיב אחד (שם וסכום או אחוז).");
      }
    }
    setSaving(true);
    try {
      if (agreement) {
        if (!title.trim()) { setSaving(false); return setError("יש להזין שם להסכם."); }
        if (!publicId.trim()) { setSaving(false); return setError("יש להזין מזהה להסכם."); }
        await editAgreement(agreement.agreement_id,
          { title: title.trim(), agreement_id: publicId.trim(), payer_name: blank(payer), partner_name: blank(partner),
            partner_percent: blank(percent) });
      } else {
        await createAgreement({
          client_name: clientId, title: title.trim(), payer_name: blank(payer), partner_name: blank(partner),
          partner_percent: blank(percent), components: [payloadOf(component)],
        });
      }
      await onSaved();
    } catch (e) {
      if (e instanceof AuthError) throw e;
      setError(describeError(e));
    } finally {
      setSaving(false);
    }
  };
  const prefix = agreement ? "agreement-edit" : "agreement-new";
  return (
    <View testID={`${prefix}-form`} style={{ gap: 6, padding: 8, borderWidth: 1, borderColor: theme.border, borderRadius: 8 }}>
      <Text style={{ color: theme.text, fontWeight: "700", textAlign: "right" }}>
        {agreement ? "עריכת הסכם" : "הסכם חדש"}
      </Text>
      <Field value={title} onChange={setTitle} placeholder="שם ההסכם" theme={theme} testID={`${prefix}-title`} />
      {agreement ? (
        <Field value={publicId} onChange={setPublicId} placeholder="מזהה ההסכם" theme={theme} testID={`${prefix}-agreement_id`} />
      ) : null}
      <Field value={payer} onChange={setPayer} placeholder="שם המשלם" theme={theme} testID={`${prefix}-payer_name`} />
      <Field value={partner} onChange={setPartner} placeholder="שם השותף" theme={theme} testID={`${prefix}-partner_name`} />
      <Field value={percent} onChange={setPercent} placeholder="אחוז שותף" theme={theme} testID={`${prefix}-partner_percent`} />
      {agreement ? null : (
        <View style={{ gap: 4 }}>
          <Text style={{ color: theme.textDim, fontSize: 12, textAlign: "right" }}>רכיב ראשון</Text>
          {COMPONENT_FIELDS.map(([key, label]) => (
            <Field key={key} value={component[key]} onChange={(v) => setComponent({ ...component, [key]: v })}
                   placeholder={label} theme={theme} testID={`${prefix}-component-${key}`} />
          ))}
        </View>
      )}
      {error ? <Text testID={`${prefix}-error`} style={{ color: theme.danger, fontSize: 12 }}>{error}</Text> : null}
      <View style={{ flexDirection: "row", gap: 8 }}>
        <Button label={saving ? "…" : "שמור"} theme={theme} testID={`${prefix}-save`} onPress={submit} disabled={saving} />
        <Button label="ביטול" theme={theme} variant="ghost" testID={`${prefix}-cancel`} onPress={onCancel} />
      </View>
    </View>
  );
}

function ComponentRow({
  agreement, component, theme, onChanged, onError,
}: {
  agreement: Agreement; component: AgreementComponent; theme: Theme;
  onChanged: () => Promise<void>; onError: (m: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const key = component.component_key;
  const run = async (fn: () => Promise<unknown>) => {
    onError(null);
    try {
      await fn();
      await onChanged();
    } catch (e) {
      if (e instanceof AuthError) throw e;
      onError(describeError(e));
    }
  };
  const act = (action: "activate" | "complete" | "cancel" | "reopen") =>
    run(() => setComponentStatus(agreement.agreement_id, key, action));
  const agreementActive = agreement.status === "Active";
  const status = component.status;
  const closed = status === "Completed" || status === "Cancelled";
  const t = (role: Role) => tone(theme, role, true);
  return (
    <View testID={`component-${key}`} style={{ gap: 4, paddingVertical: 6, borderTopWidth: 1, borderColor: theme.border }}>
      <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}>
        <View style={{ flex: 1, flexDirection: "row", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <Text testID={`component-label-${key}`} style={{ color: theme.text, fontWeight: "700" }}>{component.label}</Text>
          <Text testID={`component-amount-${key}`} style={{ color: theme.text }}>{amountText(component)}</Text>
        </View>
        <Strip
          edit={<IconButton icon="pen" title="עריכת רכיב" theme={theme} disabled={component.locked} testID={`component-edit-${key}`}
                            onPress={() => setEditing(true)} {...t("edit")} />}
          mid={status === "Pending" && agreementActive ? (
            <IconButton icon="play" title="סמן רכיב כפעיל" theme={theme} testID={`component-activate-${key}`}
                        onPress={() => act("activate")} {...t("complete")} />
          ) : status === "Active" && agreementActive ? (
            <IconButton icon="check" title="סמן רכיב כהושלם" theme={theme} testID={`component-complete-${key}`}
                        onPress={() => act("complete")} {...t("complete")} />
          ) : closed ? (
            <IconButton icon="undo" title={agreementActive ? "פתח רכיב מחדש" : "יש לפתוח את ההסכם מחדש תחילה"} theme={theme}
                        disabled={!agreementActive} testID={`component-reopen-${key}`}
                        onPress={() => act("reopen")} {...t("edit")} />
          ) : null}
          cancel={(status === "Pending" || status === "Active") && agreementActive ? (
            <IconButton icon="x" title="ביטול רכיב" theme={theme} testID={`component-cancel-${key}`}
                        onPress={() => act("cancel")} {...t("cancel")} />
          ) : null}
          last={<IconButton icon="trash" title="מחיקת רכיב" theme={theme} disabled={component.locked} testID={`component-delete-${key}`}
                            onPress={() => setConfirmDelete(true)} {...t("trash")} />}
        />
        <StatusBadge status={status} label={COMPONENT_STATUS_LABEL[status]} testID={`component-status-${key}`} theme={theme} />
      </View>
      <View testID={`component-details-${key}`} style={{ flexDirection: "row", gap: 12, flexWrap: "wrap" }}>
        {component.description ? (
          <Text style={{ color: theme.textDim, fontSize: 12 }}>{component.description}</Text>
        ) : null}
        {component.trigger_condition ? (
          <Text style={{ color: theme.textDim, fontSize: 12 }}>תנאי: {component.trigger_condition}</Text>
        ) : null}
        <Text testID={`component-vat-${key}`} style={{ color: theme.textDim, fontSize: 12 }}>{vatText(component)}</Text>
      </View>
      {confirmDelete ? (
        <View testID={`component-confirm-${key}`} style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
          <Text style={{ color: theme.text }}>למחוק את הרכיב?</Text>
          <Button label="כן, מחק" theme={theme} variant="danger" testID={`component-confirm-yes-${key}`}
                  onPress={() => { setConfirmDelete(false); run(() => deleteComponent(agreement.agreement_id, key)); }} />
          <Button label="לא" theme={theme} variant="ghost" testID={`component-confirm-no-${key}`} onPress={() => setConfirmDelete(false)} />
        </View>
      ) : null}
      {editing ? (
        <ComponentForm title="עריכת רכיב" initial={draftOf(component)} theme={theme} testPrefix={`component-edit-${key}`}
          onCancel={() => setEditing(false)}
          onSave={async (d) => {
            await editComponent(agreement.agreement_id, key, payloadOf(d));
            setEditing(false);
            await onChanged();
          }} />
      ) : null}
    </View>
  );
}

function AgreementCard({
  agreement, theme, onChanged,
}: { agreement: Agreement; theme: Theme; onChanged: () => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = agreement.agreement_id;
  const changed = onChanged;
  const status = async (action: "complete" | "cancel" | "reopen") => {
    setError(null);
    try {
      await setAgreementStatus(id, action);
      await changed();
    } catch (e) {
      if (e instanceof AuthError) throw e;
      setError(describeError(e));
    }
  };
  const active = agreement.status === "Active";
  const t = (role: Role) => tone(theme, role, false);
  return (
    <View testID={`agreement-${id}`} style={{ gap: 6, padding: 8, borderWidth: 1, borderColor: theme.border, borderRadius: 8 }}>
      <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}>
        <View style={{ flex: 1, flexDirection: "row", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <Text testID={`agreement-title-${id}`} style={{ color: theme.text, fontWeight: "800" }}>{agreement.title}</Text>
          <Text style={{ color: theme.textDim, fontSize: 11 }}>{id}</Text>
        </View>
        <Strip
          edit={<IconButton icon="pen" title="עריכת הסכם" theme={theme} testID={`agreement-edit-${id}`}
                            onPress={() => setEditing(true)} {...t("edit")} />}
          mid={active ? (
            <IconButton icon="check" title="סמן הסכם כהושלם" theme={theme} testID={`agreement-complete-${id}`}
                        onPress={() => status("complete")} {...t("complete")} />
          ) : (
            <IconButton icon="undo" title="פתח הסכם מחדש" theme={theme} testID={`agreement-reopen-${id}`}
                        onPress={() => status("reopen")} {...t("edit")} />
          )}
          cancel={active ? (
            <IconButton icon="x" title="ביטול הסכם" theme={theme} testID={`agreement-cancel-${id}`}
                        onPress={() => status("cancel")} {...t("cancel")} />
          ) : null}
          last={<IconButton icon="plus" title={active ? "הוספת רכיב" : "יש לפתוח את ההסכם מחדש כדי להוסיף רכיב"} theme={theme}
                            disabled={!active} testID={`component-add-${id}`}
                            onPress={() => setAdding(true)} {...t("add")} />}
        />
        <StatusBadge status={agreement.status} label={AGREEMENT_STATUS_LABEL[agreement.status]} testID={`agreement-status-${id}`} theme={theme} />
      </View>
      <View style={{ flexDirection: "row", gap: 14, flexWrap: "wrap" }}>
        <Text testID={`agreement-payer-${id}`} style={{ color: theme.text, fontSize: 13 }}>משלם: {agreement.payer_name || "—"}</Text>
        <Text testID={`agreement-partner-${id}`} style={{ color: theme.text, fontSize: 13 }}>שותף: {agreement.partner_name || "—"}</Text>
        <Text testID={`agreement-partner-percent-${id}`} style={{ color: theme.text, fontSize: 13 }}>
          אחוז שותף: {agreement.partner_percent != null ? `${agreement.partner_percent}%` : "—"}
        </Text>
      </View>
      {error ? <Text testID={`agreement-error-${id}`} style={{ color: theme.danger, fontSize: 12 }}>{error}</Text> : null}
      {editing ? (
        <AgreementForm theme={theme} clientId={agreement.client_name} agreement={agreement}
          onCancel={() => setEditing(false)} onSaved={async () => { setEditing(false); await changed(); }} />
      ) : null}
      {agreement.components.map((c) => (
        <ComponentRow key={c.component_key} agreement={agreement} component={c} theme={theme}
                      onChanged={changed} onError={setError} />
      ))}
      {adding ? (
        <ComponentForm title="רכיב חדש" initial={EMPTY_COMPONENT} theme={theme} testPrefix={`component-add-${id}`}
          onCancel={() => setAdding(false)}
          onSave={async (d) => { await addComponent(id, payloadOf(d)); setAdding(false); await changed(); }} />
      ) : null}
    </View>
  );
}

export default function AgreementsSection({
  clientId, theme, onAuthErr, onTotalsChanged,
}: {
  clientId: string; theme: Theme; onAuthErr: (e: unknown) => void; onTotalsChanged: () => void;
}) {
  const [agreements, setAgreements] = useState<Agreement[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      setAgreements(await fetchClientAgreements(clientId));
      setError(null);
    } catch (e) {
      if (e instanceof AuthError) return onAuthErr(e);
      setAgreements(null);
      setError(e instanceof AgreementsApiError && e.code === "agreements_unavailable"
        ? e.message : "טעינת ההסכמים נכשלה. נסו שוב מאוחר יותר.");
    }
  }, [clientId, onAuthErr]);

  useEffect(() => { load(); }, [load]);

  // A write changes the agreed total on the row above, so re-read the report too.
  const changed = async () => { await load(); onTotalsChanged(); };
  const guarded = (fn: () => Promise<void>) => async () => {
    try { await fn(); } catch (e) { if (e instanceof AuthError) onAuthErr(e); else throw e; }
  };

  return (
    <View testID="agreements-section" style={{ gap: 8 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text style={{ color: theme.text, fontWeight: "800", fontSize: 15 }}>הסכמים</Text>
        <IconButton icon="plus" title="הסכם חדש" theme={theme} testID="agreement-new" disabled={!!error}
                    onPress={() => setCreating(true)} {...NEW_AGREEMENT_TONE(theme)} />
      </View>
      {error ? <Text testID="agreements-error" style={{ color: theme.danger }}>{error}</Text> : null}
      {agreements && agreements.length === 0 ? (
        <Text testID="agreements-empty" style={{ color: theme.textDim, textAlign: "center" }}>אין הסכמים ללקוח זה</Text>
      ) : null}
      {creating ? (
        <AgreementForm theme={theme} clientId={clientId} agreement={null}
          onCancel={() => setCreating(false)} onSaved={guarded(async () => { setCreating(false); await changed(); })} />
      ) : null}
      {(agreements || []).map((a) => (
        <AgreementCard key={a.agreement_id} agreement={a} theme={theme} onChanged={guarded(changed)} />
      ))}
    </View>
  );
}
