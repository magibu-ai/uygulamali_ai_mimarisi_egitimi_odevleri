// Python (Flask) API'sine giden ince istemci.
// Backend adresini .env.local içindeki NEXT_PUBLIC_API_URL ile değiştirebilirsiniz.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

export async function mesajGonder(mesaj) {
  const res = await fetch(`${API_URL}/sohbet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mesaj }),
  });
  if (!res.ok) throw new Error(`API hatası: ${res.status}`);
  return res.json(); // { cevap, araclar: [{ad, arg, sonuc}] }
}

export async function yeniSohbet() {
  await fetch(`${API_URL}/yeni`, { method: "POST" });
}
