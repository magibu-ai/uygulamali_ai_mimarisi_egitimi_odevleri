// Sade metin biçimlendirici: markdown bağlantılarını `[metin](url)` ve çıplak
// http(s) linklerini tıklanabilir <a> öğelerine çevirir. Ağır bir markdown
// kütüphanesine gerek kalmadan RAG kaynaklarını tıklanabilir yapar.
// (Yalnızca http/https'e izin verilir; başka bir biçimlendirme uygulanmaz.)

// [metin](url)  ya da  çıplak https://...  yakalar.
const DESEN = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s)]+)/g;

function baglanti(href, metin, key) {
  return (
    <a
      key={key}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-brand-600 underline decoration-brand-500/40 underline-offset-2 hover:text-brand-700 break-words"
    >
      {metin}
    </a>
  );
}

export function metinBicimle(metin = "") {
  const parcalar = [];
  let son = 0;
  let m;
  let i = 0;
  DESEN.lastIndex = 0;
  while ((m = DESEN.exec(metin)) !== null) {
    if (m.index > son) parcalar.push(metin.slice(son, m.index));
    if (m[2]) {
      // [metin](url) biçimi
      parcalar.push(baglanti(m[2], m[1], i++));
    } else if (m[3]) {
      // çıplak url — sondaki noktalama işaretini bağlantıdan çıkar
      let url = m[3];
      let kuyruk = "";
      while (/[.,;:)]$/.test(url)) {
        kuyruk = url.slice(-1) + kuyruk;
        url = url.slice(0, -1);
      }
      parcalar.push(baglanti(url, url, i++));
      if (kuyruk) parcalar.push(kuyruk);
    }
    son = DESEN.lastIndex;
  }
  if (son < metin.length) parcalar.push(metin.slice(son));
  return parcalar;
}
