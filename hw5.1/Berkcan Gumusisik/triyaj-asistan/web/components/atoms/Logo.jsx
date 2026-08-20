// Atom: uygulama logosu (amblem + isim).
export default function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-600 text-2xl shadow-sm">
        🏥
      </div>
      <div className="leading-tight">
        <div className="text-lg font-extrabold text-slate-900">Triyaj Asistanı</div>
        <div className="text-xs text-slate-500">Yerel LLM · Türkçe sağlık yönlendirme</div>
      </div>
    </div>
  );
}
