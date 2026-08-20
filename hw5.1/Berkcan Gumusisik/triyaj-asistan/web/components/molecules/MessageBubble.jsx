import UrgencyBadge from "@/components/atoms/UrgencyBadge";
import ToolChip from "@/components/molecules/ToolChip";
import { aciliyetDuzeyi } from "@/lib/tools";
import { metinBicimle } from "@/lib/format";

// Molekül: tek bir sohbet balonu (kullanıcı ya da asistan).
// Asistan balonunda, çağrılan araçlar ve varsa aciliyet rozeti gösterilir.
export default function MessageBubble({ role, text, tools = [] }) {
  const kullanici = role === "user";

  // Araç sonuçlarından aciliyet düzeyini bul (varsa).
  const aciliyet = tools
    .map((t) => aciliyetDuzeyi(t.sonuc))
    .find(Boolean);

  return (
    <div className={`flex w-full ${kullanici ? "justify-end" : "justify-start"}`}>
      <div className={`flex max-w-[80%] flex-col gap-2 ${kullanici ? "items-end" : "items-start"}`}>
        {!kullanici && tools.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {tools.map((t, i) => (
              <ToolChip key={i} ad={t.ad} arg={t.arg} />
            ))}
          </div>
        )}

        {aciliyet && <UrgencyBadge level={aciliyet} />}

        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
            kullanici
              ? "rounded-br-md bg-brand-600 text-white"
              : "rounded-bl-md border border-slate-100 bg-white text-slate-800"
          }`}
        >
          {kullanici ? text : metinBicimle(text)}
        </div>
      </div>
    </div>
  );
}
