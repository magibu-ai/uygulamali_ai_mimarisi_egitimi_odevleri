// Araç adı -> arayüzde gösterilecek etiket, ikon ve kısa açıklama.
export const ARAC_BILGISI = {
  aciliyet_degerlendir: {
    etiket: "Aciliyet Değerlendirme",
    ikon: "🚦",
    aciklama: "Belirtileri kural tabanlı puanlar",
  },
  tibbi_bilgi_ara: {
    etiket: "Tıbbi Bilgi Arama (RAG)",
    ikon: "📚",
    aciklama: "Gerçek hastane makalelerinden bilgi getirir",
  },
  internet_arama: {
    etiket: "İnternet Araması",
    ikon: "🔎",
    aciklama: "DuckDuckGo ile web araması",
  },
  yakin_saglik_kurulusu: {
    etiket: "Yakın Sağlık Kuruluşu",
    ikon: "🏥",
    aciklama: "OpenStreetMap ile en yakın hastane/eczane",
  },
  hesap_makinesi: {
    etiket: "Hesap Makinesi",
    ikon: "🧮",
    aciklama: "Ayrı Python süreciyle (subprocess) hesaplama",
  },
};

export function aracBilgisi(ad) {
  return (
    ARAC_BILGISI[ad] || { etiket: ad, ikon: "🔧", aciklama: "Araç" }
  );
}

// aciliyet_degerlendir çıktısındaki emojiden aciliyet düzeyini çıkarır.
export function aciliyetDuzeyi(sonuc = "") {
  if (sonuc.includes("🔴")) return "acil";
  if (sonuc.includes("🟠")) return "bugun";
  if (sonuc.includes("🟢")) return "dusuk";
  return null;
}
