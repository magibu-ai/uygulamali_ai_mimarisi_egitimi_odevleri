import Header from "@/components/organisms/Header";
import MessageList from "@/components/organisms/MessageList";
import ChatInput from "@/components/molecules/ChatInput";
import DisclaimerBanner from "@/components/molecules/DisclaimerBanner";

// Şablon (template): sayfanın iskeleti. Veri/olay almaz, yalnızca yerleşimi
// kurar ve parçaları birbirine bağlar. Durum yönetimi pages katmanındadır.
export default function ChatTemplate({
  messages,
  loading,
  onSend,
  onReset,
  onPick,
}) {
  return (
    <div className="flex h-[100dvh] w-full flex-col">
      <Header onReset={onReset} />

      <main className="flex flex-1 flex-col overflow-hidden">
        <MessageList messages={messages} loading={loading} onPick={onPick} />
      </main>

      <footer className="space-y-2 border-t border-slate-200 bg-white/70 px-4 py-3 backdrop-blur">
        <DisclaimerBanner />
        <ChatInput onSend={onSend} disabled={loading} />
      </footer>
    </div>
  );
}
