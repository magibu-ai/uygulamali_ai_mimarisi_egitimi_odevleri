const API_URL = "http://127.0.0.1:8000";


// =========================================================
// DOM ELEMENTLERİ
// =========================================================

const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const chatMessages = document.getElementById("chatMessages");

const basvuruListesi = document.getElementById("basvuruListesi");

const toplamBasvuru = document.getElementById("toplamBasvuru");
const basvurulduSayisi = document.getElementById("basvurulduSayisi");
const mulakatSayisi = document.getElementById("mulakatSayisi");
const reddedildiSayisi = document.getElementById("reddedildiSayisi");

const toolPanel = document.getElementById("toolPanel");
const toolList = document.getElementById("toolList");
const toolPanelClose = document.getElementById("toolPanelClose");

const suggestionButtons = document.querySelectorAll(
    ".suggestion-button"
);


// =========================================================
// SOHBET GEÇMİŞİ
// =========================================================

let conversationMessages = null;


// =========================================================
// UYGULAMA BAŞLANGICI
// =========================================================

document.addEventListener("DOMContentLoaded", async () => {

    await basvurulariYukle();
    await istatistikleriYukle();

});


// =========================================================
// BAŞVURULARI GETİR
// =========================================================

async function basvurulariYukle() {

    try {

        const response = await fetch(
            `${API_URL}/api/basvurular`
        );

        if (!response.ok) {
            throw new Error(
                "Başvurular alınamadı."
            );
        }

        const data = await response.json();

        basvuruListesi.innerHTML = "";

        const sonuclar = data.sonuclar || [];

        if (sonuclar.length === 0) {

            basvuruListesi.innerHTML = `
                <div class="empty-state">
                    Henüz kayıtlı başvuru yok.
                </div>
            `;

            return;
        }

        sonuclar.forEach((basvuru) => {

            const card = document.createElement("div");

            card.className = "application-card";

            card.innerHTML = `
                <h3>${escapeHTML(basvuru.sirket)}</h3>

                <p>
                    ${escapeHTML(basvuru.pozisyon)}
                </p>

                <span class="application-status">
                    ${escapeHTML(basvuru.durum)}
                </span>
            `;

            basvuruListesi.appendChild(card);

        });

    }

    catch (error) {

        console.error(error);

        basvuruListesi.innerHTML = `
            <div class="empty-state">
                Başvurular yüklenemedi.
            </div>
        `;

    }

}


// =========================================================
// İSTATİSTİKLERİ GETİR
// =========================================================

async function istatistikleriYukle() {

    try {

        const response = await fetch(
            `${API_URL}/api/istatistikler`
        );

        if (!response.ok) {
            throw new Error(
                "İstatistikler alınamadı."
            );
        }

        const data = await response.json();

        const durumlar =
            data.durumlara_gore || {};

        toplamBasvuru.textContent =
            data.toplam_basvuru || 0;

        basvurulduSayisi.textContent =
            durumlar["Başvuruldu"] || 0;

        mulakatSayisi.textContent =
            durumlar["Mülakat"] || 0;

        reddedildiSayisi.textContent =
            durumlar["Reddedildi"] || 0;

    }

    catch (error) {

        console.error(
            "İstatistik hatası:",
            error
        );

    }

}


// =========================================================
// CHAT FORM
// =========================================================

chatForm.addEventListener(
    "submit",
    async (event) => {

        event.preventDefault();

        const message =
            messageInput.value.trim();

        if (!message) {
            return;
        }

        await mesajGonder(message);

    }
);


// =========================================================
// ÖNERİ BUTONLARI
// =========================================================

suggestionButtons.forEach((button) => {

    button.addEventListener(
        "click",
        async () => {

            const message =
                button.dataset.message;

            if (!message) {
                return;
            }

            await mesajGonder(message);

        }
    );

});


// =========================================================
// MESAJ GÖNDER
// =========================================================

async function mesajGonder(message) {

    kullaniciMesajiEkle(message);

    messageInput.value = "";

    mesajAlaniniBoyutlandir();

    sendButton.disabled = true;

    const loadingElement =
        loadingMesajiEkle();

    try {

        const response = await fetch(
            `${API_URL}/api/chat`,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    message: message,
                    messages: conversationMessages
                })
            }
        );

        if (!response.ok) {
            throw new Error(
                "Backend isteği başarısız."
            );
        }

        const data = await response.json();

        loadingElement.remove();

        if (
            data.messages &&
            Array.isArray(data.messages)
        ) {
            conversationMessages =
                data.messages;
        }

        assistantMesajiEkle(
            data.cevap ||
            "Modelden cevap alınamadı."
        );

        toolGoster(
            data.tools_used || []
        );

        // Tool başvuru verisini değiştirmiş olabilir.
        // Sidebar'ı tekrar güncelle.
        await basvurulariYukle();
        await istatistikleriYukle();

    }

    catch (error) {

        console.error(error);

        loadingElement.remove();

        assistantMesajiEkle(
            "Backend ile bağlantı kurulamadı. " +
            "FastAPI sunucusunun çalıştığından emin olun."
        );

    }

    finally {

        sendButton.disabled = false;

        messageInput.focus();

    }

}


// =========================================================
// KULLANICI MESAJI
// =========================================================

function kullaniciMesajiEkle(message) {

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "message user-message";

    wrapper.innerHTML = `
        <div class="message-content">

            <div class="message-header">
                Sen
            </div>

            <div class="message-text">
                ${escapeHTML(message)}
            </div>

        </div>

        <div class="message-avatar">
            👤
        </div>
    `;

    chatMessages.appendChild(wrapper);

    chatAlaniniAltaKaydir();

}


// =========================================================
// ASISTAN MESAJI
// =========================================================

function assistantMesajiEkle(message) {

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "message assistant-message";

    wrapper.innerHTML = `
        <div class="message-avatar">
            🚀
        </div>

        <div class="message-content">

            <div class="message-header">
                Kariyer Copilotu
            </div>

            <div class="message-text">
                ${formatMessage(message)}
            </div>

        </div>
    `;

    chatMessages.appendChild(wrapper);

    chatAlaniniAltaKaydir();

}


// =========================================================
// LOADING
// =========================================================

function loadingMesajiEkle() {

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "message assistant-message loading-message";

    wrapper.innerHTML = `
        <div class="message-avatar">
            🚀
        </div>

        <div class="message-content">

            <div class="message-header">
                Kariyer Copilotu
            </div>

            <div class="message-text">
                Düşünüyor...
            </div>

        </div>
    `;

    chatMessages.appendChild(wrapper);

    chatAlaniniAltaKaydir();

    return wrapper;

}


// =========================================================
// TOOL PANEL
// =========================================================

function toolGoster(tools) {

    toolList.innerHTML = "";

    if (!tools || tools.length === 0) {

        toolPanel.classList.add("hidden");

        return;
    }

    tools.forEach((tool) => {

        const item =
            document.createElement("div");

        item.className = "tool-item";

        item.innerHTML = `
            <strong>
                🔧 ${escapeHTML(tool.name)}
            </strong>

            <pre>${escapeHTML(
                JSON.stringify(
                    tool.arguments || {},
                    null,
                    2
                )
            )}</pre>
        `;

        toolList.appendChild(item);

    });

    toolPanel.classList.remove("hidden");

}


toolPanelClose.addEventListener(
    "click",
    () => {

        toolPanel.classList.add(
            "hidden"
        );

    }
);


// =========================================================
// TEXTAREA OTOMATİK BOYUT
// =========================================================

messageInput.addEventListener(
    "input",
    mesajAlaniniBoyutlandir
);


function mesajAlaniniBoyutlandir() {

    messageInput.style.height = "auto";

    messageInput.style.height =
        `${Math.min(
            messageInput.scrollHeight,
            130
        )}px`;

}


// =========================================================
// ENTER İLE GÖNDER
// SHIFT + ENTER İLE ALT SATIR
// =========================================================

messageInput.addEventListener(
    "keydown",
    (event) => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            chatForm.requestSubmit();

        }

    }
);


// =========================================================
// CHAT SCROLL
// =========================================================

function chatAlaniniAltaKaydir() {

    chatMessages.scrollTop =
        chatMessages.scrollHeight;

}


// =========================================================
// BASİT MESAJ FORMATLAMA
// =========================================================

function formatMessage(text) {

    if (!text) {
        return "";
    }

    let safeText =
        escapeHTML(text);

    // **kalın**
    safeText = safeText.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );

    // Satır sonları
    safeText = safeText.replace(
        /\n/g,
        "<br>"
    );

    return safeText;

}


// =========================================================
// HTML GÜVENLİĞİ
// =========================================================

function escapeHTML(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

}