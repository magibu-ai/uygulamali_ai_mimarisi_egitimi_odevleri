"""Tek kaynakli prompt dosyasi.

MASTER = tum sistemin ortak tanimi (alan, kalite kurallari).
Iki asama bunun uzerine kisa gorev eki alir:  1) soru uretimi  2) cevap+thinking.
"""

MASTER = """Sen MATEMATIK alaninda "Tool Call" (fonksiyon cagirma) egitim verisi ureten bir
veri seti mimarisin.

ALANIN TANIMI:
Bir dil modelinin, kendisine verilen matematik fonksiyonlarini DOGRU sekilde cagirmasini
ve donen sonucu kullaniciya UYGUN bicimde sunmasini ogretmek. Iki beceri birlikte olculur:
  1) Dogru arac secimi + dogru parametre cikarimi (gereksiz cagri yapmamak dahil).
  2) Ham sayisal ciktiyi kullaniciya net, dogal ve eksiksiz anlatmak.

ARAC TASARIMI:
Araclar hesaplama araclaridir; ornegin evaluate_expression, solve_equation,
compute_derivative, definite_integral, matrix_multiply, descriptive_stats,
combinations, compound_interest, convert_unit, factorize, gcd_lcm, triangle_area.
Parametreler matematiksel ifadeleri duz metin olarak alir (orn. "3*x^2 - 5*x + 2").

DEGISMEZ KURALLAR:
- Cikti DAIMA gecerli JSON. Markdown kod bloklari, aciklama metni, ``` isareti YOK.
- Tum kullaniciya donuk metinler {lang_name} dilinde. Fonksiyon ve parametre isimleri
  ingilizce snake_case (orn: solve_equation, lower_bound).
- Fonksiyon semalari JSON Schema uyumlu: type/properties/required alanlari eksiksiz,
  her parametrenin "description" alani dolu.
- MATEMATIKSEL DOGRULUK sart: sayilar tutarli olmali, ara adimlar ve nihai sonuc
  gercekten dogru cikmali. Sonucu uydurma, hesabi yap.
- Gercekci ve cesitli ol: ayni kaliptaki cumleleri ve ayni sayilari tekrarlama.
"""

QUESTION_TASK = """
GOREV: Asagidaki basliga ait {count} adet BIRBIRINDEN FARKLI ornek uret.

  Alt alan : {domain}
  Konu     : {topic}
  Senaryo  : {scenario} -> {scenario_desc}
  Zorluk   : {difficulty}

Her ornek icin sunlari uret:
- tools        : Modele sunulan 2-4 matematik fonksiyonu. Sadece 1-2 tanesi gercekten
                 gerekli olsun, digerleri inandirici celdirici olsun.
- user_message : Kullanicinin dogal, gunluk dille yazdigi tek mesaj. "Su fonksiyonu cagir"
                 gibi acik talimat ICERMEZ; ogrenci/muhendis/esnaf gibi gercek bir kullanici
                 nasil sorarsa oyle sorar. Zorluk arttikca problem baglami zenginlesir.
- expected_tools: Bu senaryoda cagrilmasi beklenen fonksiyon isimleri (senaryo
                 "eksik_parametre" veya "arac_gereksiz" ise bos liste).

Cikti semasi (tam olarak bu):
{{"items":[{{"tools":[{{"type":"function","function":{{"name":"...","description":"...",
"parameters":{{"type":"object","properties":{{}},"required":[]}}}}}}],
"user_message":"...","expected_tools":["..."]}}]}}
"""

ANSWER_TASK = """
GOREV: Asagidaki ornek icin ideal model davranisini uret.

  Alt alan: {domain}
  Konu    : {topic}
  Senaryo : {scenario} -> {scenario_desc}
  Zorluk  : {difficulty}

KULLANILABILIR FONKSIYONLAR:
{tools_json}

KULLANICI MESAJI:
{user_message}

Uretecegin alanlar:
- thinking     : Birinci tekil sahis, 3-6 cumle ic muhakeme. Sirasiyla: kullanici ne
                 istiyor, hangi arac neden secildi (ya da neden hicbiri secilmedi),
                 parametreler mesajdan nasil cikarildi, sonuc nasil sunulacak.
                 Hesabin ara adimlarini burada acikca goster ve dogrula.
- tool_calls   : Yapilan cagrilar, sirayla. Her biri {{"name","arguments"}}.
                 Arac cagrilmayacaksa bos liste.
- tool_results : Her cagrinin donmesi beklenen GERCEKCI ve MATEMATIKSEL OLARAK DOGRU
                 sonucu {{"name","result"}}. Senaryo "hata_yonetimi" ise result icinde
                 hata bilgisi olsun (orn. sifira bolme, negatif diskriminant).
- answer       : Kullaniciya verilecek son yanit. Ham JSON yapistirma; sonucu cumle
                 icinde acikla, sayilari birimleriyle ver, gerekiyorsa kisa liste kullan.
                 Senaryo "eksik_parametre" ise tek ve net bir netlestirme sorusu sor.

Cikti semasi (tam olarak bu):
{{"thinking":"...","tool_calls":[{{"name":"...","arguments":{{}}}}],
"tool_results":[{{"name":"...","result":{{}}}}],"answer":"..."}}
"""

LANG_NAMES = {"tr": "Turkce", "en": "Ingilizce"}


def system_prompt(lang: str = "tr") -> str:
    return MASTER.format(lang_name=LANG_NAMES.get(lang, "Turkce"))


def question_prompt(**kw) -> str:
    return QUESTION_TASK.format(**kw)


def answer_prompt(**kw) -> str:
    return ANSWER_TASK.format(**kw)
