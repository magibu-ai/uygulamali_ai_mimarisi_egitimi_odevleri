// Molekül: tıklanınca sohbete gönderilen örnek soru çipi.
export default function ExampleChip({ metin, onClick }) {
  return (
    <button
      type="button"
      onClick={() => onClick(metin)}
      className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 shadow-sm transition hover:border-brand-500 hover:text-brand-700"
    >
      {metin}
    </button>
  );
}
