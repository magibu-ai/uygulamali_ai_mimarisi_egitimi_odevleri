import { aracBilgisi } from "@/lib/tools";

// Molekül: modelin çağırdığı bir aracı gösteren çip.
export default function ToolChip({ ad, arg }) {
  const bilgi = aracBilgisi(ad);
  const argMetni = arg && Object.keys(arg).length
    ? Object.values(arg).filter(Boolean).join(" · ")
    : "";
  return (
    <div className="inline-flex max-w-full items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
      <span>{bilgi.ikon}</span>
      <span className="font-semibold text-slate-700">{bilgi.etiket}</span>
      {argMetni && (
        <span className="truncate text-slate-400" title={argMetni}>
          — {argMetni}
        </span>
      )}
    </div>
  );
}
