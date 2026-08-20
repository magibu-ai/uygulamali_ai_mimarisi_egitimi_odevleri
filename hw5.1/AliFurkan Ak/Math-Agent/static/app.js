/**
 * MathAgent Frontend - Sohbet & İstemci Taraflı (Client-Side) Hesaplama Motoru
 */

document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const statusBadge = document.getElementById('statusBadge');
    const statusText = document.getElementById('statusText');

    let messageHistory = [];

    // 1. Ollama Servis Durum Kontrolü
    async function checkHealth() {
        try {
            const healthRes = await fetch('/api/health');
            if (healthRes.ok) {
                statusBadge.classList.add('online');
                statusBadge.classList.remove('offline');
                statusText.textContent = 'Aktif';
            } else {
                throw new Error('API yanıt vermiyor');
            }
        } catch (err) {
            statusBadge.classList.add('offline');
            statusBadge.classList.remove('online');
            statusText.textContent = 'Bağlantı Kesildi';
        }
    }

    checkHealth();
    setInterval(checkHealth, 15000);

    // 2. Textarea Otomatik Yükseklik Ayarı
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight) + 'px';
    });

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Hızlı prompt butonları için küresel fonksiyon
    window.sendQuickPrompt = (promptText) => {
        userInput.value = promptText;
        userInput.style.height = 'auto';
        chatForm.dispatchEvent(new Event('submit'));
    };

    // 3. İSTEMCİ TARAFINDA (CLIENT-SIDE) JS KODU EXECUTE ETME MOTORU
    function executeClientSideJS(code, functionName, args = []) {
        const startTime = performance.now();
        try {
            let executableCode = code + "\n";
            
            // Fonksiyon adı verilmişse çağrıyı ekle
            if (functionName && functionName.trim()) {
                const cleanFn = functionName.trim();
                executableCode += `\nif (typeof ${cleanFn} === 'function') { return ${cleanFn}.apply(null, ${JSON.stringify(args)}); }`;
            } else {
                // Kod içindeki ilk fonksiyon tanımını otomatik bul
                const fnMatch = code.match(/function\s+([a-zA-Z0-9_$]+)/);
                if (fnMatch && fnMatch[1]) {
                    const foundFn = fnMatch[1];
                    executableCode += `\nif (typeof ${foundFn} === 'function') { return ${foundFn}.apply(null, ${JSON.stringify(args)}); }`;
                } else if (!code.includes('return')) {
                    // Kod içinde return yoksa sarmalla
                    executableCode = `return (function() {\n${code}\n})();`;
                }
            }

            // Tarayıcı içinde dinamik güvenli fonksiyon oluşturma
            const runner = new Function(executableCode);
            const rawResult = runner();
            const endTime = performance.now();

            let formattedResult = rawResult;
            if (typeof rawResult === 'bigint') {
                formattedResult = rawResult.toString();
            } else if (typeof rawResult === 'object' && rawResult !== null) {
                formattedResult = JSON.stringify(rawResult, null, 2);
            } else if (rawResult === undefined) {
                formattedResult = "İşlem başarıyla tamamlandı.";
            }

            return {
                success: true,
                result: formattedResult,
                executionTimeMs: (endTime - startTime).toFixed(2)
            };
        } catch (err) {
            const endTime = performance.now();
            return {
                success: false,
                error: err.message || String(err),
                executionTimeMs: (endTime - startTime).toFixed(2)
            };
        }
    }

    // 4. Form Gönderimi ve Sohbet Akışı
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;

        // Kullanıcı Mesajını Ekle
        appendUserMessage(text);
        messageHistory.push({ role: 'user', content: text });

        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;

        // Typing indicator ekle
        const typingEl = appendTypingIndicator();
        scrollToBottom();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    messages: messageHistory
                })
            });

            typingEl.remove();

            if (!res.ok) {
                throw new Error(`Sunucu Hatası: ${res.statusText}`);
            }

            const responseData = await res.json();
            handleAgentResponse(responseData);

        } catch (err) {
            typingEl.remove();
            appendErrorMessage(`Bir hata oluştu: ${err.message}. Servis bağlantısını kontrol edin.`);
        } finally {
            sendBtn.disabled = false;
            scrollToBottom();
        }
    });

    // 5. Ajan Yanıtını İşleme
    function handleAgentResponse(data) {
        if (data.type === 'tool_call') {
            // MATEMATİK TOOL-CALL: LLM Kodu üretti, Tarayıcıda çalıştıracağız!
            const { filename, description, code, function_name, args, file_url } = data;

            // CLIENT-SIDE EXECUTION
            const execResult = executeClientSideJS(code, function_name, args);

            // Asistan yanıtını ekrana kart olarak bas
            appendToolCallMessage({
                filename,
                description,
                code,
                file_url,
                execResult
            });

            // Geçmişe asistan cevabını ekle
            messageHistory.push({
                role: 'assistant',
                content: `Sonuç: ${execResult.result}`
            });

        } else if (data.type === 'web_search') {
            // DUCKDUCKGO WEB SEARCH TOOL-CALL
            const { query, results } = data;
            appendWebSearchMessage({ query, results });
            messageHistory.push({
                role: 'assistant',
                content: `Arama sonuçları (${query}): ${results.map(r => r.title + ": " + r.snippet).join(" | ")}`
            });
        } else if (data.type === 'text') {
            // Düz metin yanıtı (Selamlaşma veya Guardrail Reddi)
            const textContent = data.message;
            appendAssistantTextMessage(textContent);
            messageHistory.push({ role: 'assistant', content: textContent });
        } else if (data.type === 'error') {
            appendErrorMessage(data.message);
        }
    }

    // --- DOM Oluşturma Yardımcıları ---

    function appendUserMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message user-message';
        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-user"></i></div>
            <div class="message-content">${escapeHTML(text)}</div>
        `;
        chatMessages.appendChild(msgDiv);
    }

    function appendAssistantTextMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message';
        
        // Eğer metinde kod bloğu kaldıysa ekrana basılmaması için temizle
        const cleanText = text.replace(/```(?:javascript|js)?\s*[\s\S]*?```/g, '').trim();
        if (!cleanText) return;

        // Eğer guardrail reddi ise özel uyarı kartı
        const isRejection = cleanText.includes("yalnızca matematiksel hesaplamalar");

        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content">
                ${isRejection ? `
                    <div class="rejection-box">
                        <i class="fa-solid fa-circle-info" style="font-size: 18px;"></i>
                        <div>${escapeHTML(cleanText)}</div>
                    </div>
                ` : `
                    <p style="line-height: 1.6; white-space: pre-wrap;">${escapeHTML(cleanText)}</p>
                `}
            </div>
        `;
        chatMessages.appendChild(msgDiv);
    }

    function appendToolCallMessage({ filename, description, code, file_url, execResult }) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message';

        const isSuccess = execResult.success;
        const resultHeaderIcon = isSuccess ? 'fa-circle-check' : 'fa-circle-xmark';
        const resultTitle = isSuccess ? 'HESAPLAMA SONUCU' : 'HESAPLAMA HATASI';

        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-calculator"></i></div>
            <div class="message-content">
                <p style="font-weight: 600; margin-bottom: 8px; color: var(--accent-cyan);">
                    ${escapeHTML(description)}
                </p>
                
                <div class="tool-execution-card">
                    <div class="result-box ${isSuccess ? '' : 'error'}">
                        <div class="result-header">
                            <i class="fa-solid ${resultHeaderIcon}"></i> ${resultTitle}
                        </div>
                        <div class="result-content">${escapeHTML(isSuccess ? execResult.result : execResult.error)}</div>
                    </div>
                </div>
            </div>
        `;
        chatMessages.appendChild(msgDiv);
    }

    function appendWebSearchMessage({ query, results }) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message';

        let resultsHTML = '';
        if (results && results.length > 0) {
            resultsHTML = results.map(r => `
                <div class="web-search-item" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px; margin-top: 8px;">
                    <a href="${escapeHTML(r.url)}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-cyan); font-weight: 600; text-decoration: none; font-size: 14px; display: block; margin-bottom: 4px;">
                        <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 11px;"></i> ${escapeHTML(r.title)}
                    </a>
                    <p style="font-size: 13px; color: var(--text-secondary); margin: 0; line-height: 1.4;">${escapeHTML(r.snippet)}</p>
                </div>
            `).join('');
        } else {
            resultsHTML = '<p style="color: var(--text-secondary); font-size: 13px;">Matematiksel arama sonucu bulunamadı.</p>';
        }

        msgDiv.innerHTML = `
            <div class="avatar" style="background: var(--accent-purple);"><i class="fa-solid fa-magnifying-glass"></i></div>
            <div class="message-content">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-weight: 600; color: var(--accent-purple);">
                    <i class="fa-solid fa-globe"></i> Matematiksel Web Araması: <em>"${escapeHTML(query)}"</em>
                </div>
                <div class="web-search-results">
                    ${resultsHTML}
                </div>
            </div>
        `;
        chatMessages.appendChild(msgDiv);
    }

    function appendErrorMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant-message';
        msgDiv.innerHTML = `
            <div class="avatar" style="background: var(--accent-rose);"><i class="fa-solid fa-circle-exclamation"></i></div>
            <div class="message-content" style="border-color: rgba(244, 63, 94, 0.4);">
                <p style="color: #fca5a5; font-weight: 500;">${escapeHTML(text)}</p>
            </div>
        `;
        chatMessages.appendChild(msgDiv);
    }

    function appendTypingIndicator() {
        const div = document.createElement('div');
        div.className = 'message assistant-message';
        div.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <span style="font-size: 12px; color: var(--text-secondary); margin-left: 8px;">Hesaplama hazırlanıyor...</span>
                </div>
            </div>
        `;
        chatMessages.appendChild(div);
        return div;
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function escapeHTML(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
});
