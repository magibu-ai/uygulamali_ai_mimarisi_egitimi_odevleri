"use client";

import { useState } from "react";
import Button from "@/components/atoms/Button";

// Molekül: mesaj yazma alanı + gönder düğmesi.
// Enter ile gönderir, Shift+Enter ile yeni satır açar.
export default function ChatInput({ onSend, disabled }) {
  const [deger, setDeger] = useState("");

  function gonder() {
    const metin = deger.trim();
    if (!metin || disabled) return;
    onSend(metin);
    setDeger("");
  }

  return (
    <div className="flex items-end gap-2">
      <textarea
        rows={1}
        value={deger}
        disabled={disabled}
        onChange={(e) => setDeger(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            gonder();
          }
        }}
        placeholder="Şikâyetinizi ya da sorunuzu yazın… (örn. 2 gündür ateşim var)"
        className="max-h-40 min-h-[48px] flex-1 resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm outline-none focus:border-brand-500"
      />
      <Button onClick={gonder} disabled={disabled} className="h-12 px-5">
        Gönder
      </Button>
    </div>
  );
}
