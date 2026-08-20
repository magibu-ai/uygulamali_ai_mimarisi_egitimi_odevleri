/* e-hekim frontend.
 *
 * Credential handling: the API key lives in the value of a password input and
 * in a local variable for the duration of one fetch. It is never written to
 * localStorage, sessionStorage, a cookie, the URL, or the document — so it
 * cannot survive a reload, leak through the browser history, or appear in the
 * server's access log. It travels in the X-Provider-Key request header.
 *
 * Rendering: every value that came from the server or the corpus is inserted
 * with textContent, never innerHTML.
 */
(function () {
  "use strict";

  var el = function (id) { return document.getElementById(id); };

  var state = {
    mode: "search",
    config: null,
    busy: false
  };

  var nodes = {
    modeSearch: el("mode-search"),
    modeRag: el("mode-rag"),
    ragSettings: el("rag-settings"),
    form: el("query-form"),
    query: el("query"),
    threshold: el("threshold"),
    thresholdOut: el("threshold-out"),
    topK: el("top-k"),
    provider: el("provider"),
    model: el("model"),
    apiKey: el("api-key"),
    keyHint: el("key-hint"),
    consoleLink: el("console-link"),
    includeReasoning: el("include-reasoning"),
    submit: el("submit-btn"),
    clear: el("clear-btn"),
    status: el("status"),
    error: el("error"),
    answerCard: el("answer-card"),
    answerBody: el("answer-body"),
    refusalNote: el("refusal-note"),
    reasoningWrap: el("reasoning-wrap"),
    reasoningBody: el("reasoning-body"),
    usage: el("usage"),
    resultsSection: el("results-section"),
    results: el("results"),
    resultsMeta: el("results-meta"),
    resultsHeading: el("results-heading"),
    statChunks: el("stat-chunks"),
    statModel: el("stat-model"),
    statDim: el("stat-dim")
  };

  /* ---------- helpers ---------- */

  function setHidden(node, hidden) {
    if (hidden) { node.setAttribute("hidden", ""); } else { node.removeAttribute("hidden"); }
  }

  function showError(message) {
    nodes.error.textContent = message;
    setHidden(nodes.error, false);
  }

  function clearError() {
    nodes.error.textContent = "";
    setHidden(nodes.error, true);
  }

  function setStatus(text) {
    nodes.status.textContent = text || "";
  }

  function setBusy(busy) {
    state.busy = busy;
    nodes.submit.disabled = busy;
    nodes.submit.textContent = busy
      ? "Çalışıyor…"
      : (state.mode === "rag" ? "Yanıt üret" : "Ara");
  }

  function formatScore(value) {
    return (typeof value === "number") ? value.toFixed(4) : "—";
  }

  /* ---------- configuration ---------- */

  function applyConfig(config) {
    state.config = config;

    nodes.statChunks.textContent = config.chunk_count.toLocaleString("tr-TR");
    nodes.statModel.textContent = config.embedding_model.split("/").pop();
    nodes.statDim.textContent = String(config.embedding_dim);

    nodes.threshold.value = String(config.default_threshold);
    nodes.thresholdOut.textContent = Number(config.default_threshold).toFixed(2);
    nodes.topK.value = String(config.default_top_k);
    nodes.topK.max = String(config.max_top_k);
    nodes.query.maxLength = config.max_query_chars;

    config.providers.forEach(function (provider) {
      var option = document.createElement("option");
      option.value = provider.id;
      option.textContent = provider.label;
      nodes.provider.appendChild(option);
    });

    var defaultProvider = (config.default_model_key || "").split(":")[0];
    if (defaultProvider) { nodes.provider.value = defaultProvider; }
    populateModels();

    if (config.chunk_count === 0) {
      showError(
        "Vektör veritabanı boş görünüyor. Önce `uv run python scripts/ingest.py` komutunu çalıştırın."
      );
    }
  }

  function currentProvider() {
    if (!state.config) { return null; }
    var id = nodes.provider.value;
    var found = null;
    state.config.providers.forEach(function (p) { if (p.id === id) { found = p; } });
    return found;
  }

  function populateModels() {
    var provider = currentProvider();
    nodes.model.textContent = "";
    if (!provider) { return; }

    provider.models.forEach(function (model) {
      var option = document.createElement("option");
      option.value = model.key;
      option.textContent = model.label + " — " + model.family +
        (model.supports_thinking ? " (thinking)" : "");
      nodes.model.appendChild(option);
    });

    if (state.config.default_model_key) {
      var hasDefault = provider.models.some(function (m) {
        return m.key === state.config.default_model_key;
      });
      if (hasDefault) { nodes.model.value = state.config.default_model_key; }
    }

    nodes.keyHint.textContent = provider.key_hint || "";
    nodes.consoleLink.href = provider.console_url || "#";
  }

  /* ---------- mode ---------- */

  function setMode(mode) {
    state.mode = mode;
    var isRag = (mode === "rag");

    nodes.modeRag.classList.toggle("is-active", isRag);
    nodes.modeSearch.classList.toggle("is-active", !isRag);
    nodes.modeRag.setAttribute("aria-checked", String(isRag));
    nodes.modeSearch.setAttribute("aria-checked", String(!isRag));

    setHidden(nodes.ragSettings, !isRag);
    setHidden(nodes.answerCard, true);
    setBusy(false);
  }

  /* ---------- rendering ---------- */

  function tierClass(result, threshold) {
    if (result.similarity === null || result.similarity === undefined) { return "sim-context"; }
    if (result.passed_threshold === false) { return "is-rejected"; }
    return (result.similarity >= threshold + 0.08) ? "sim-high" : "sim-mid";
  }

  function renderResult(result, threshold) {
    var item = document.createElement("li");
    item.className = "result " + tierClass(result, threshold);

    var head = document.createElement("div");
    head.className = "result-head";

    var heading = document.createElement("p");
    heading.className = "result-title";
    if (result.citation) {
      var marker = document.createElement("span");
      marker.className = "citation";
      marker.textContent = "[" + result.citation + "]";
      heading.appendChild(marker);
    }
    if (result.url) {
      var link = document.createElement("a");
      link.href = result.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = result.title || "Başlıksız";
      heading.appendChild(link);
    } else {
      heading.textContent = result.title || "Başlıksız";
    }

    var score = document.createElement("div");
    score.className = "score";
    var isContextOnly = (result.similarity === null || result.similarity === undefined);
    var scoreValue = document.createElement("span");
    scoreValue.className = "score-value";
    scoreValue.textContent = isContextOnly ? "—" : formatScore(result.similarity);
    var scoreLabel = document.createElement("span");
    scoreLabel.className = "score-label";
    scoreLabel.textContent = isContextOnly ? "komşu bölüm" : "kosinüs";
    score.appendChild(scoreValue);
    score.appendChild(scoreLabel);

    head.appendChild(heading);
    head.appendChild(score);
    item.appendChild(head);

    var meta = document.createElement("div");
    meta.className = "result-meta";
    [
      result.source,
      "parça " + result.chunk_index,
      "id " + result.chunk_id
    ].forEach(function (text) {
      if (!text) { return; }
      var tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = text;
      meta.appendChild(tag);
    });
    if (result.passed_threshold === false) {
      var rejected = document.createElement("span");
      rejected.className = "tag rejected";
      rejected.textContent = "eşiğin altında";
      meta.appendChild(rejected);
    } else if (isContextOnly) {
      var contextTag = document.createElement("span");
      contextTag.className = "tag context";
      contextTag.textContent = "bağlam için eklendi";
      meta.appendChild(contextTag);
    }
    item.appendChild(meta);

    var body = document.createElement("p");
    body.className = "result-text";
    body.textContent = result.chunk_text;
    item.appendChild(body);

    if (result.url) {
      var urlWrap = document.createElement("span");
      urlWrap.className = "result-url";
      var urlLink = document.createElement("a");
      urlLink.href = result.url;
      urlLink.target = "_blank";
      urlLink.rel = "noopener noreferrer";
      urlLink.textContent = result.url;
      urlWrap.appendChild(urlLink);
      item.appendChild(urlWrap);
    }

    return item;
  }

  function renderResults(payload) {
    nodes.results.textContent = "";

    // In RAG mode show the passages the model actually cited, numbered exactly
    // as its [n] markers. In search mode show the scored hits.
    var usingContext = Boolean(payload.context && payload.context.length);
    var items = usingContext ? payload.context : (payload.results || []);

    nodes.resultsHeading.textContent = usingContext
      ? "Yanıtın dayandığı bölümler"
      : "Kaynak parçalar";

    if (items.length === 0) {
      var empty = document.createElement("li");
      empty.className = "empty";
      empty.textContent = "Vektör veritabanından hiç sonuç dönmedi.";
      nodes.results.appendChild(empty);
    } else {
      items.forEach(function (item) {
        nodes.results.appendChild(renderResult(item, payload.threshold));
      });
    }

    var all = payload.results || [];
    var passed = all.filter(function (r) { return r.passed_threshold; }).length;
    var meta = passed + " / " + all.length + " parça eşiği geçti · eşik " +
      Number(payload.threshold).toFixed(2) +
      " · en yüksek benzerlik " + formatScore(payload.best_similarity);
    if (usingContext) {
      meta += " · modele " + payload.context.length + " bölüm gönderildi";
    }
    nodes.resultsMeta.textContent = meta;

    setHidden(nodes.resultsSection, false);
  }

  var REFUSAL_EXPLANATION = {
    below_threshold:
        "Benzerlik eşiğinin altında kalındı — dil modeli hiç çağrılmadı, " +
        "bu yanıtı sistem üretti.",
    model_insufficient_context:
        "Parçalar eşiği geçti, ancak model sorunun cevabını belgelerde bulamadı " +
        "ve kendi bilgisinden yanıt üretmeyi reddetti."
  };

  function renderAnswer(payload) {
    nodes.answerBody.textContent = payload.answer;
    nodes.answerBody.classList.toggle("is-refusal", Boolean(payload.refused));

    var explanation = REFUSAL_EXPLANATION[payload.refusal_reason] || "";
    nodes.refusalNote.textContent = explanation;
    setHidden(nodes.refusalNote, !explanation);

    if (payload.reasoning) {
      nodes.reasoningBody.textContent = payload.reasoning;
      setHidden(nodes.reasoningWrap, false);
    } else {
      nodes.reasoningBody.textContent = "";
      setHidden(nodes.reasoningWrap, true);
    }

    var bits = [];
    if (payload.model) { bits.push("model: " + payload.model); }
    if (payload.context_passages) { bits.push("bağlam: " + payload.context_passages + " parça"); }
    if (payload.usage) {
      if (payload.usage.prompt_tokens != null) { bits.push("girdi: " + payload.usage.prompt_tokens); }
      if (payload.usage.completion_tokens != null) { bits.push("çıktı: " + payload.usage.completion_tokens); }
      if (payload.usage.reasoning_tokens != null) { bits.push("düşünme: " + payload.usage.reasoning_tokens); }
    }
    nodes.usage.textContent = bits.join(" · ");
    setHidden(nodes.answerCard, false);
  }

  /* ---------- requests ---------- */

  function readErrorDetail(response) {
    return response.json().then(
      function (data) { return (data && data.detail) ? data.detail : ("Sunucu hatası (" + response.status + ")."); },
      function () { return "Sunucu hatası (" + response.status + ")."; }
    );
  }

  function submit(event) {
    event.preventDefault();
    if (state.busy) { return; }

    clearError();
    setHidden(nodes.answerCard, true);

    var query = nodes.query.value.trim();
    if (!query) {
      showError("Lütfen bir soru yazın.");
      return;
    }

    var body = {
      query: query,
      top_k: Number(nodes.topK.value),
      threshold: Number(nodes.threshold.value)
    };

    var headers = { "Content-Type": "application/json" };
    var endpoint = "/api/search";

    if (state.mode === "rag") {
      // Read the key straight from the input into a local; it is not retained.
      var apiKey = nodes.apiKey.value.trim();
      if (!apiKey) {
        showError("RAG modu için sağlayıcı API anahtarınızı girin. Anahtarsız değerlendirme için 'Anlamsal Arama' modunu kullanabilirsiniz.");
        return;
      }
      endpoint = "/api/ask";
      headers["X-Provider-Key"] = apiKey;
      body.model_key = nodes.model.value;
      body.include_reasoning = nodes.includeReasoning.checked;
    }

    setBusy(true);
    setStatus(state.mode === "rag" ? "Belgeler getiriliyor ve model çağrılıyor…" : "Aranıyor…");

    fetch(endpoint, {
      method: "POST",
      headers: headers,
      body: JSON.stringify(body),
      cache: "no-store",
      referrerPolicy: "no-referrer"
    }).then(function (response) {
      if (!response.ok) {
        return readErrorDetail(response).then(function (detail) { throw new Error(detail); });
      }
      return response.json();
    }).then(function (payload) {
      renderResults(payload);
      if (state.mode === "rag") {
        renderAnswer(payload);
      } else if (!payload.grounded && payload.notice) {
        // Keyless mode: surface the same refusal the RAG path would produce.
        renderAnswer({ answer: payload.notice, refused: true });
      }
      setStatus("");
    }).catch(function (err) {
      showError(err && err.message ? err.message : "Beklenmeyen bir hata oluştu.");
      setStatus("");
    }).then(function () {
      setBusy(false);
    });
  }

  function clearAll() {
    nodes.query.value = "";
    nodes.apiKey.value = "";
    nodes.results.textContent = "";
    nodes.answerBody.textContent = "";
    setHidden(nodes.resultsSection, true);
    setHidden(nodes.answerCard, true);
    clearError();
    setStatus("");
    nodes.query.focus();
  }

  /* ---------- wiring ---------- */

  nodes.modeSearch.addEventListener("click", function () { setMode("search"); });
  nodes.modeRag.addEventListener("click", function () { setMode("rag"); });
  nodes.threshold.addEventListener("input", function () {
    nodes.thresholdOut.textContent = Number(nodes.threshold.value).toFixed(2);
  });
  nodes.provider.addEventListener("change", populateModels);
  nodes.form.addEventListener("submit", submit);
  nodes.clear.addEventListener("click", clearAll);

  // Ctrl/Cmd+Enter submits from the textarea.
  nodes.query.addEventListener("keydown", function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      nodes.form.requestSubmit();
    }
  });

  // Belt and braces: if the tab is closed or reloaded, drop the key from the
  // DOM so it cannot be restored by the browser's form-state restoration.
  window.addEventListener("pagehide", function () { nodes.apiKey.value = ""; });

  fetch("/api/config", { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) { throw new Error("Yapılandırma alınamadı."); }
      return response.json();
    })
    .then(applyConfig)
    .catch(function () {
      showError("Sunucu yapılandırması alınamadı. Arka uç çalışıyor mu?");
    });

  setMode("search");
})();
