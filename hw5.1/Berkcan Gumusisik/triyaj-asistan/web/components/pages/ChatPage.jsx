"use client";

import { useState } from "react";
import ChatTemplate from "@/components/templates/ChatTemplate";
import { mesajGonder, yeniSohbet } from "@/lib/api";

// Sayfa (page): tüm durum ve iş mantığı burada toplanır; alt katmanlar
// (template/organisms/…) yalnızca props ile beslenen sunum bileşenleridir.
export default function ChatPage() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  async function gonder(metin) {
    setMessages((m) => [...m, { role: "user", text: metin }]);
    setLoading(true);
    try {
      const veri = await mesajGonder(metin);
      setMessages((m) => [
        ...m,
        { role: "assistant", text: veri.cevap, tools: veri.araclar || [] },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text:
            "Bağlantı hatası: API'ye ulaşılamadı. 'python3 app.py' çalışıyor mu?",
          tools: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function sifirla() {
    await yeniSohbet().catch(() => {});
    setMessages([]);
  }

  return (
    <ChatTemplate
      messages={messages}
      loading={loading}
      onSend={gonder}
      onReset={sifirla}
      onPick={gonder}
    />
  );
}
