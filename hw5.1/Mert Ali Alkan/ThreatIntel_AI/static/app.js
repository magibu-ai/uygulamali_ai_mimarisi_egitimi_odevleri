const chatBox = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let chatHistory = [];

userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Auto-resize textarea
userInput.addEventListener('input', function() {
    sendBtn.disabled = this.value.trim() === '';
    this.style.height = '64px';
    const newHeight = Math.min(this.scrollHeight, 120);
    this.style.height = newHeight + 'px';
});

sendBtn.addEventListener('click', function(e) {
    e.preventDefault();
    sendMessage();
});

function getToolIcon(toolName) {
    if (toolName === "check_virustotal") return "fa-bug";
    if (toolName === "check_rdap") return "fa-globe";
    if (toolName === "search_phishing_rag") return "fa-brain";
    if (toolName === "auto_risk_score") return "fa-chart-pie";
    if (toolName === "analyze_email") return "fa-envelope-open-text";
    if (toolName === "extract_urls") return "fa-link";
    return "fa-gear";
}

function getToolColor(toolName) {
    if (toolName === "check_virustotal") return "text-soft-red";
    if (toolName === "check_rdap") return "text-electric-blue";
    if (toolName === "search_phishing_rag") return "text-soft-orange";
    if (toolName === "auto_risk_score") return "text-purple-500";
    return "text-electric-blue";
}

function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // Append User Message (Clean, standard chat bubble)
    const userMsgHtml = `
    <div class="flex justify-end w-full mt-6">
        <div class="bg-inverse-on-surface text-on-surface px-5 py-3 rounded-2xl rounded-tr-sm max-w-[80%] whitespace-pre-wrap font-body-base">
            ${text}
        </div>
    </div>`;
    chatBox.insertAdjacentHTML('beforeend', userMsgHtml);

    userInput.value = '';
    sendBtn.disabled = true;
    scrollToBottom();

    // Create System Response Container
    const systemId = 'sys-' + Date.now();
    const systemHtml = `
    <div id="${systemId}" class="flex flex-col gap-3 w-full max-w-[95%] mt-6">
        <div class="flex items-start gap-4">
            <i class="fa-solid fa-robot text-electric-blue text-3xl mt-1 shrink-0"></i>
            <div class="flex-1 flex flex-col gap-3 min-w-0" id="sys-content-${systemId}">
                
                <!-- Tools Accordion -->
                <details id="tools-details-${systemId}" class="bg-[#111114] border border-glass-border rounded-xl hidden overflow-hidden w-full max-w-2xl">
                    <summary class="px-4 py-3 text-sm font-medium text-on-surface-variant cursor-pointer hover:bg-white/5 transition-colors flex items-center gap-2 list-none" style="list-style: none;">
                        <span class="material-symbols-outlined text-electric-blue animate-spin" id="tools-spinner-${systemId}">sync</span>
                        <span id="tools-title-${systemId}">Analiz yapılıyor...</span>
                    </summary>
                    <div id="tool-cards-${systemId}" class="p-4 flex flex-col gap-3 border-t border-glass-border bg-[#0a0a0c]">
                        <!-- Tool cards appended here vertically -->
                    </div>
                </details>

                <!-- Final Report / Text -->
                <div id="report-${systemId}" class="prose font-body-base text-on-surface w-full max-w-none hidden mt-2">
                     <!-- text here -->
                </div>
            </div>
        </div>
    </div>`;
    
    chatBox.insertAdjacentHTML('beforeend', systemHtml);
    scrollToBottom();

    const toolsDetails = document.getElementById(`tools-details-${systemId}`);
    const toolCards = document.getElementById(`tool-cards-${systemId}`);
    const reportDiv = document.getElementById(`report-${systemId}`);
    const toolsSpinner = document.getElementById(`tools-spinner-${systemId}`);
    const toolsTitle = document.getElementById(`tools-title-${systemId}`);

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, history: [] })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let done = false;

        let activeTools = {};
        let toolCount = 0;

        while (!done) {
            const { value, done: readerDone } = await reader.read();
            done = readerDone;
            if (value) {
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            
                            if (data.type === 'tool_call') {
                                toolsDetails.classList.remove('hidden');
                                toolsDetails.open = true; // Keep open while running
                                const iconClass = getToolColor(data.name);
                                
                                const feedItemId = `feed-${systemId}-${data.name}`;
                                activeTools[data.name] = feedItemId;
                                
                                // Insert loading row
                                toolCards.insertAdjacentHTML('beforeend', `
                                <div id="${feedItemId}" class="text-sm font-mono-data text-outline flex items-center gap-2">
                                    <span class="material-symbols-outlined animate-spin text-[16px] ${iconClass}">sync</span>
                                    <span class="${iconClass}">${data.name} çalıştırılıyor...</span>
                                </div>`);
                                scrollToBottom();
                            } 
                            else if (data.type === 'tool_result') {
                                toolCount++;
                                const feedItemId = activeTools[data.name];
                                const faIcon = getToolIcon(data.name);
                                const colorClass = getToolColor(data.name);
                                
                                let resultText = data.result;

                                const completedCardHtml = `
                                <div class="flex flex-col gap-2 border border-glass-border rounded-lg p-3 bg-black/50 w-full">
                                    <div class="flex justify-between items-center text-sm">
                                        <span class="${colorClass} font-medium flex items-center gap-2"><i class="fa-solid ${faIcon}"></i> ${data.name}</span>
                                        <span class="text-[10px] text-electric-blue font-mono-data tracking-wider">DONE</span>
                                    </div>
                                    <div class="text-xs text-on-surface-variant font-mono-data max-h-32 overflow-y-auto whitespace-pre-wrap">${resultText}</div>
                                </div>`;

                                // Replace the loading row with the completed card
                                if (feedItemId) {
                                    const feedItem = document.getElementById(feedItemId);
                                    if (feedItem) {
                                        feedItem.outerHTML = completedCardHtml;
                                    }
                                } else {
                                    toolCards.insertAdjacentHTML('beforeend', completedCardHtml);
                                }
                                scrollToBottom();
                            }
                            else if (data.type === 'think') {
                                // Extract the think text
                                const thinkText = data.content;
                                
                                // Create a visual block for thinking
                                const thinkHtml = `
                                <div class="flex flex-col gap-2 border border-glass-border rounded-lg p-4 bg-black/40 w-full mb-3 backdrop-blur-sm animate-fade-in shadow-[inset_0_0_15px_rgba(255,255,255,0.02)]">
                                    <div class="flex items-center gap-2 text-xs font-semibold tracking-wider text-on-surface-variant/80 uppercase">
                                        <i class="fa-solid fa-brain text-electric-blue animate-pulse"></i> 
                                        <span>Yapay Zeka Düşünüyor...</span>
                                    </div>
                                    <div class="text-[13px] text-on-surface-variant/90 font-mono max-h-48 overflow-y-auto whitespace-pre-wrap italic leading-relaxed scrollbar-thin">${thinkText}</div>
                                </div>`;
                                
                                // Insert it into the UI. If tools exist and tools section is visible, put it there. Otherwise in the chat.
                                if (toolsDetails && !toolsDetails.classList.contains('hidden')) {
                                    toolCards.insertAdjacentHTML('afterbegin', thinkHtml);
                                } else {
                                    reportDiv.insertAdjacentHTML('beforebegin', thinkHtml);
                                }
                                scrollToBottom();
                            }
                            else if (data.type === 'report') {
                                // Finalize tools UI
                                toolsSpinner.textContent = 'check_circle';
                                toolsSpinner.classList.remove('animate-spin');
                                toolsTitle.textContent = `${toolCount} araç kullanılarak analiz edildi.`;
                                toolsDetails.open = false; // Auto close tools

                                reportDiv.classList.remove('hidden');
                                
                                // Render Markdown
                                reportDiv.innerHTML = marked.parse(data.content);
                                scrollToBottom();
                            }
                            else if (data.type === 'error') {
                                reportDiv.classList.remove('hidden');
                                reportDiv.innerHTML = `<span class="text-soft-red">Hata: ${data.content}</span>`;
                                scrollToBottom();
                            }
                        } catch (e) {
                            console.error("Error parsing SSE JSON", e, line);
                        }
                    }
                }
            }
        }
    } catch (error) {
        reportDiv.classList.remove('hidden');
        reportDiv.innerHTML = `<span class="text-soft-red">Bağlantı hatası: Sunucuya ulaşılamadı.</span>`;
    } finally {
        sendBtn.disabled = userInput.value.trim() === '';
        userInput.style.height = '64px'; // Reset height
        userInput.focus();
        scrollToBottom();
    }
}
