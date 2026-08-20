import ExampleChip from "@/components/molecules/ExampleChip";

// Her çip, farklı bir aracı tetikleyecek şekilde seçildi.
const ORNEKLER = [
  "2 gündür göğsümde baskı var ve sol koluma yayılıyor",
  "inme (felç) belirtileri nelerdir?",
  "boğazım hafif ağrıyor, ateşim yok",
  "Ankara'da yakın hastaneler neler?",
];

// Organizma: boş ekranda gösterilen örnek soru çipleri.
export default function ExamplePrompts({ onPick }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <div className="text-4xl">🩺</div>
      <h2 className="text-base font-semibold text-slate-700">
        Nasıl yardımcı olabilirim?
      </h2>
      <p className="max-w-md text-sm text-slate-500">
        Bir şikâyetinizi anlatın ya da bir sağlık sorusu sorun. Aciliyeti
        değerlendirir, doğru bölüme yönlendiririm.
      </p>
      <div className="mt-2 flex max-w-xl flex-wrap justify-center gap-2">
        {ORNEKLER.map((m) => (
          <ExampleChip key={m} metin={m} onClick={onPick} />
        ))}
      </div>
    </div>
  );
}
