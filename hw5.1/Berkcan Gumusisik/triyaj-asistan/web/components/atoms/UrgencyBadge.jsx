// Atom: aciliyet düzeyi rozeti (🔴 acil / 🟠 bugün / 🟢 düşük).
const DUZEY = {
  acil: { metin: "ACİL — 112", nokta: "bg-acil", cerceve: "border-red-200 bg-red-50 text-red-700" },
  bugun: { metin: "BUGÜN GÖRÜLMELİ", nokta: "bg-bugun", cerceve: "border-orange-200 bg-orange-50 text-orange-700" },
  dusuk: { metin: "DÜŞÜK ACİLİYET", nokta: "bg-dusuk", cerceve: "border-green-200 bg-green-50 text-green-700" },
};

export default function UrgencyBadge({ level }) {
  const d = DUZEY[level];
  if (!d) return null;
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-bold ${d.cerceve}`}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${d.nokta}`} />
      {d.metin}
    </span>
  );
}
