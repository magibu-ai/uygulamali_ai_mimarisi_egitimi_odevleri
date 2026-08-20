"use client";

import { useEffect, useRef } from "react";
import MessageBubble from "@/components/molecules/MessageBubble";
import Spinner from "@/components/atoms/Spinner";
import ExamplePrompts from "@/components/organisms/ExamplePrompts";

// Organizma: kaydırılabilir mesaj listesi. Boşsa örnekleri gösterir,
// yeni mesajda otomatik en alta kayar.
export default function MessageList({ messages, loading, onPick }) {
  const sonRef = useRef(null);

  useEffect(() => {
    sonRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  if (messages.length === 0 && !loading) {
    return (
      <div className="ince-scroll flex-1 overflow-y-auto px-4">
        <ExamplePrompts onPick={onPick} />
      </div>
    );
  }

  return (
    <div className="ince-scroll flex-1 space-y-4 overflow-y-auto px-4 py-5">
      {messages.map((m, i) => (
        <MessageBubble key={i} role={m.role} text={m.text} tools={m.tools} />
      ))}
      {loading && (
        <div className="flex justify-start">
          <div className="rounded-2xl rounded-bl-md border border-slate-100 bg-white px-4 py-3 shadow-sm">
            <Spinner />
          </div>
        </div>
      )}
      <div ref={sonRef} />
    </div>
  );
}
