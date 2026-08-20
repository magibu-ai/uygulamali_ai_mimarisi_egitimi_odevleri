"""
Giresun kültürel özellikleri - olgu tabanı (fact base).

Bu olgular web kaynaklarından derlenmiştir. Her Q&A çifti bu olgulara
dayandırılarak üretilir; model uydurma bilgi üretmemesi için cevaplar
buradaki içeriğe sıkı biçimde bağlıdır.

Kaynaklar:
- T.C. Giresun Valiliği (giresun.gov.tr/giresun-kulturu, /kultur-ve-sanat)
- Doğu Karadeniz Kültür Envanteri Projesi (karadeniz.gov.tr)
- tr.wikipedia.org/wiki/Giresun_Adası
- Giresun İl Kültür ve Turizm Müdürlüğü kaynaklı derlemeler (KÜRE Ansiklopedi vb.)
- Giresun TSO, yerel basın (gastronomi festivali, kemençe/horon festivali)
"""

# Her giriş bir "konu" ve o konuya ait doğrulanmış olgu cümlelerinden oluşur.
FACTS = {
    "genel": [
        "Giresun, Türkiye'nin Karadeniz Bölgesi'nde yer alan bir ildir.",
        "Giresun'un plaka numarası 28'dir.",
        "Giresun'un 15 ilçesi vardır: Piraziz, Bulancak, Keşap, Espiye, Tirebolu, Görele, Eynesil, Alucra, Çamoluk, Çanakçı, Dereli, Doğankent, Güce, Şebinkarahisar ve Yağlıdere.",
        "Giresun'un komşu illeri doğuda Trabzon ve Gümüşhane, batıda Ordu, güneyde Erzincan ve Sivas'tır; kuzeyinde Karadeniz bulunur.",
        "Arkeolojik araştırmalara göre Giresun şehrinin milattan önce 350'li yıllarda kurulduğu belirtilir.",
        "Giresun tarih boyunca birçok medeniyete ev sahipliği yapmış köklü bir yerleşimdir.",
    ],
    "findik": [
        "Fındık, Giresun ile özdeşleşmiş en önemli tarım ürünüdür.",
        "Giresun'da fındık yalnızca bir tarım ürünü değil, aynı zamanda ekonomik ve kültürel bir değer olarak görülür.",
        "Fındık hasadı yöre halkı için hem geçim kaynağı hem de geleneksel bir süreçtir.",
        "Giresun fındığı çikolata ve şekerleme sektöründe özel bir yere sahiptir.",
        "Fındık ezmesi, fındıklı tatlılar ve fındıklı atıştırmalıklar Giresun mutfağında yaygındır.",
        "Fındık toplarken söylenen türkülere yörede 'fındık havası' denir.",
    ],
    "ada": [
        "Giresun Adası, Türkiye'nin Karadeniz kıyısındaki üzerinde bitki örtüsü bulunan tek adasıdır.",
        "Giresun Adası, şehir merkezine yaklaşık 1,6 km mesafede, yaklaşık 40.000 metrekare yüzölçümüne sahiptir.",
        "Giresun Adası ikinci derece doğal sit alanı olarak koruma altındadır.",
        "Antik dönemde Giresun Adası'nın adı Aretias olarak bilinirdi.",
        "Efsaneye göre Giresun Adası Amazon kadınları tarafından kurulmuş ve Amazon kraliçeleri savaş tanrısı Ares adına burada bir tapınak yaptırmıştır.",
        "Yunan mitolojisindeki Altın Post efsanesine göre Herkül'ün de içinde bulunduğu Argonautlar Giresun Adası'na ulaşmıştır.",
        "Adada Alexius II dönemine ait sur kalıntıları, kuleler, manastır ve tarihi pişmiş toprak fıçılar bulunur.",
        "Ada Cenevizliler ve Venedikliler tarafından uzun süre gemi sığınağı olarak kullanılmıştır.",
        "Adadaki Hamza Taşı, sacayağı biçiminde olup ana tanrıça Kybele'yi temsil eder ve halk arasında 'dilek taşı' olarak bilinir.",
        "Adada Akdeniz defnesi ve yalancı akasya başta olmak üzere 71 doğal bitki türü bulunur; ada aynı zamanda göçmen kuşların uğrak yeridir.",
    ],
    "aksu": [
        "Aksu Festivali (Uluslararası Aksu Festivali) Giresun'un en önemli geleneksel etkinliğidir.",
        "Aksu Festivali her yıl 20 Mayıs'ta düzenlenir.",
        "Aksu Festivali kapsamında Giresun Adası'nın etrafında tekne ile dolaşılır.",
        "Festivalde soyun sürdürülmesi inancıyla Hamza Taşı'nın (sacayağı) altından geçme geleneği uygulanır.",
        "Aksu Festivali'ndeki ritüeller, adanın kültürel ve mitolojik yönünü öne çıkarır.",
    ],
    "muzik": [
        "Giresun halk müziği genel olarak Karadeniz Bölgesi'nin özelliklerini taşır.",
        "Giresun oyunları içinde en önemlileri Giresun Karşılaması ve horondur.",
        "Horon, erkekler tarafından bölgenin meşhur çalgısı olan kemençe veya davul-zurna eşliğinde oynanır.",
        "Horonun düz horon, sık sara, dik horon ve sallama gibi çeşitleri vardır.",
        "Giresun, zengin kemençe geleneği nedeniyle 'kemençenin başkenti' olarak kabul edilir.",
        "Katip Şadi, Giresun yöresi kemençe ekolünün en önemli temsilcilerinden biridir.",
        "Kıyı kesiminde horon ve kemençe öne çıkarken, iç kesimlerde bağlama ve oturak havaları yaygındır.",
        "Kıyı kesiminde yalı havaları, dağlık bölgelerde yayla havaları yaygındır.",
        "Görele ilçesi kemençe kültürünün merkezlerinden biridir ve burada Uluslararası Kemençe ve Horon Festivali düzenlenir.",
        "Giresun'da çalınan ezgiler ağırlıkla 7 ve 9 zamanlıdır; 9 zamanlı ezgiler genellikle karşılama havasıdır.",
    ],
    "yemek": [
        "Giresun'un en meşhur yemekleri arasında pancar (karalahana) çorbası, fasulye turşusu ve fasulye kavurması yer alır.",
        "Karadeniz'in coğrafi şartları nedeniyle Giresun'da tahıl tarımı yerine bahçe sebzeciliği, hayvancılık yerine balıkçılık gelişmiştir.",
        "Giresun mutfağında karalahana (yörede pancar da denir), mısır, fasulye ve kabak gibi sebzeler öne çıkar.",
        "Başta hamsi olmak üzere balık ve balık yemekleri Giresun mutfağında önemli yer tutar.",
        "Giresun ismiyle anılan ürünler arasında Giresun fındığı, Giresun kirazı, Giresun pidesi, Giresun kadayıfı ve Giresun güllacı bulunur.",
        "Giresun pidesi ince hamuru ve taş fırında pişirilmesiyle öne çıkar.",
        "Yöresel lezzetler arasında ısırgan otu yemeği, galdirik kavurması, taflan kavurması, mısır ekmeği ve lahana diblesi sayılır.",
        "Giresun'un yöresel mutfağı, bol yeşillik içermesi nedeniyle 'yeşil mutfak' olarak tanıtılır ve Yeşil Lezzetleri Gastronomi Festivali ile öne çıkarılır.",
    ],
    "islik_dili": [
        "Islık dili, Giresun'un Çanakçı, Görele, Eynesil ve Tirebolu ilçelerinde yaşatılan geleneksel bir iletişim yöntemidir.",
        "Islık dili, dağlık coğrafyada kilometrelerce uzaklıktaki kişiler arasında haberleşmeyi sağlar.",
        "Islık dilini yaklaşık 10 bin kişinin konuşabildiği veya anlayabildiği tahmin edilir.",
        "Islık dili, UNESCO Acil Koruma Gerektiren Somut Olmayan Kültürel Miras Listesi'nde yer alır.",
    ],
    "kiyafet": [
        "Giresun'un yöresel kıyafetleri çevre illerle benzerlik gösterir.",
        "Geleneksel kadın giyiminde ketenden beyaz gömlek, dize kadar beyaz çorap ve gömlek üstüne fistan bulunur.",
        "Erkek giyiminde gömlek, siyah şalvar, 'alaçordup' denilen çorap ve çorap üzerine çarık yer alır.",
        "Peştamal, Giresun kadın giyiminin değişmez bir parçasıdır.",
        "Kadın kıyafetlerinde bordo, yeşil ve altın işleme renkleri; erkek kıyafetlerinde siyah ve beyaz baskındır.",
    ],
    "tarihi_yerler": [
        "Giresun Kalesi, şehrin önemli tarihi yapılarından biridir.",
        "Şebinkarahisar Kalesi ve Tirebolu Kalesi, ilin önemli tarihi kaleleri arasındadır.",
        "Sis Dağı, Kümbet, Gölyanı, Bektaş ve Kulakkaya yaylaları Giresun'un öne çıkan yaylalarıdır.",
        "Yayla kültürü Giresun'un önemli bir parçasıdır; yayla göçü ve yayla şenlikleri geleneksel eğlence ortamlarıdır.",
        "Giresun Müzesi ve Giresun Atatürk Evi ilin kültürel mekanları arasındadır.",
    ],
    "turku": [
        "Giresun türküler yönünden zengin bir ildir.",
        "Giresun türkülerinden bazıları Mican, Tamzara, Karahisar Türküsü, Fingil ve 'Aksu Derler Adına'dır.",
        "'Aynalıdır Aynalı' Giresun yöresine ait bilinen türkülerden biridir.",
    ],
    "gelenek": [
        "Giresun'da her yıl Mart ayının 14'ünde 'yılbaşı' (Nevruz benzeri mevsimlik gelenek) tutulur.",
        "Mart 14 sabahı erkenden kalkılıp deniz veya akarsudan su alınması geleneği vardır.",
        "Yayla yolculukları, otçu göçü, yayla şenlikleri, nişan ve kına düğünleri Giresun'un başlıca çalgılı eğlence ortamlarıdır.",
    ],
}
