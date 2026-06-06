import type { TriggeredEvent } from "../api/play";

type EventCardProps = {
  event: TriggeredEvent;
  onContinue: () => void;
};

function isPositiveEvent(event: TriggeredEvent): boolean {
  const effects = event.applied_effects ?? [];
  if (effects.length === 0) return true;
  return effects.every((e) => e.type !== "resource_stat" || (e.delta ?? 0) >= 0);
}

function formatEffectLine(effect: NonNullable<TriggeredEvent["applied_effects"]>[number]): string {
  if (effect.type === "resource_stat") {
    const label = effect.label_ko || effect.key;
    const delta = effect.delta ?? 0;
    const sign = delta >= 0 ? "+" : "";
    const before = effect.before ?? "?";
    const after = effect.after ?? "?";
    return `${label} ${sign}${delta} (${before} → ${after})`;
  }
  return "";
}

export function EventCard({ event, onContinue }: EventCardProps) {
  const positive = isPositiveEvent(event);
  const title = event.name || event.event_id || "이벤트";
  const effects = (event.applied_effects ?? []).filter((e) => e.type === "resource_stat");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-[fadeIn_0.3s_ease-out]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="event-card-title"
    >
      <div
        className={`w-full max-w-md rounded-xl border p-5 shadow-xl animate-[fadeIn_0.3s_ease-out] ${
          positive
            ? "border-amber-500/40 bg-gradient-to-b from-amber-950/90 to-slate-900/95"
            : "border-sky-500/40 bg-gradient-to-b from-sky-950/90 to-slate-900/95"
        }`}
      >
        <p className="mb-2 text-center text-sm font-medium text-amber-200/90">✨ {title}</p>
        {event.description ? (
          <p className="mb-4 text-center text-sm leading-relaxed text-slate-200">
            &ldquo;{event.description}&rdquo;
          </p>
        ) : null}

        {effects.length > 0 ? (
          <div className="mb-5 rounded-lg border border-slate-600/50 bg-slate-900/60 px-3 py-2 text-sm text-slate-100">
            {effects.map((eff, i) => (
              <div key={`${eff.key}-${i}`} className="py-0.5">
                {formatEffectLine(eff)}
              </div>
            ))}
          </div>
        ) : null}

        <div className="flex justify-center">
          <button
            type="button"
            onClick={onContinue}
            className="rounded-lg bg-slate-700 px-6 py-2 text-sm font-medium text-slate-100 hover:bg-slate-600"
          >
            계속
          </button>
        </div>
      </div>
    </div>
  );
}
