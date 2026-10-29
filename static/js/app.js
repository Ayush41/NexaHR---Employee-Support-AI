// NexaHR - Client Application
document.addEventListener("DOMContentLoaded", () => {
    const chatMessages = document.getElementById("chat-messages");
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");
    const btnClear = document.getElementById("btn-clear");
    const ingestForm = document.getElementById("ingest-form");
    const ingestStatus = document.getElementById("ingest-status");

    // 1. Check API Health
    async function checkHealth() {
        try {
            const res = await fetch("/api/health");
            if (res.ok) {
                statusDot.className = "status-dot online";
                statusText.textContent = "Online";
            } else {
                throw new Error();
            }
        } catch {
            statusDot.className = "status-dot offline";
            statusText.textContent = "Offline";
        }
    }
    checkHealth();
    setInterval(checkHealth, 30000);

    // 2. Auto-resize Textarea
    userInput.addEventListener("input", () => {
        userInput.style.height = "auto";
        userInput.style.height = `${Math.min(userInput.scrollHeight, 140)}px`;
    });

    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit"));
        }
    });

    // 3. Scroll to Bottom
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // 4. Append User Message
    function appendUserMessage(text) {
        const msg = document.createElement("div");
        msg.className = "message user-msg";
        msg.innerHTML = `
      <div class="avatar">You</div>
      <div class="message-content">
        <div class="message-body">${escapeHtml(text)}</div>
      </div>
    `;
        chatMessages.appendChild(msg);
        scrollToBottom();
    }

    // 5. Typing Indicator
    function showTypingIndicator() {
        const loader = document.createElement("div");
        loader.id = "typing-loader";
        loader.className = "message assistant-msg";
        loader.innerHTML = `
      <div class="avatar">N</div>
      <div class="message-content">
        <div class="typing-dots">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
        chatMessages.appendChild(loader);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        const loader = document.getElementById("typing-loader");
        if (loader) loader.remove();
    }

    // 6. Append Assistant Message
    function appendAssistantMessage(data) {
        hideTypingIndicator();
        const msg = document.createElement("div");
        msg.className = "message assistant-msg";

        // Source Badge Mapping
        let pillClass = "pill-direct";
        let pillLabel = "Direct";
        if (data.source_used === "private_kb") {
            pillClass = "pill-kb";
            pillLabel = "Private Knowledge Base";
        } else if (data.source_used === "web" || data.source_used === "web_search") {
            pillClass = "pill-web";
            pillLabel = "Web Search";
        }

        // Citations HTML
        let citationsHtml = "";
        if (data.citations && data.citations.length > 0) {
            citationsHtml = `<div class="citations-box"><strong>Sources:</strong>` +
                data.citations.map(c => `
          <a class="citation-item" href="${c.url || '#'}" target="_blank" rel="noopener">
            &bull; ${escapeHtml(c.title || "Reference")}
          </a>
        `).join("") + `</div>`;
        }

        // Execution Trace Details
        let traceHtml = "";
        if (data.trace && data.trace.length > 0) {
            traceHtml = `
        <details class="trace-details">
          <summary class="trace-summary">Agent Execution Trace (${data.trace.length} steps)</summary>
          <ul class="trace-list">
            ${data.trace.map(t => `<li>&bull; ${escapeHtml(t)}</li>`).join("")}
          </ul>
        </details>
      `;
        }

        msg.innerHTML = `
      <div class="avatar">N</div>
      <div class="message-content">
        <div class="message-body">${escapeHtml(data.answer)}</div>
        <div class="meta-row">
          <span class="source-pill ${pillClass}">${pillLabel}</span>
        </div>
        ${citationsHtml}
        ${traceHtml}
      </div>
    `;
        chatMessages.appendChild(msg);
        scrollToBottom();
    }

    // 7. Handle Chat Submission
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const query = userInput.value.trim();
        if (!query) return;

        appendUserMessage(query);
        userInput.value = "";
        userInput.style.height = "auto";
        showTypingIndicator();

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: query }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: "Failed to fetch response" }));
                throw new Error(err.detail || "Server error");
            }

            const data = await res.json();
            appendAssistantMessage(data);
        } catch (err) {
            hideTypingIndicator();
            appendAssistantMessage({
                answer: `Error: ${err.message}`,
                source_used: "direct",
            });
        }
    });

    // 8. Quick Prompts
    document.querySelectorAll(".prompt-chip").forEach((chip) => {
        chip.addEventListener("click", () => {
            userInput.value = chip.dataset.query;
            chatForm.dispatchEvent(new Event("submit"));
        });
    });

    // 9. Document Ingestion
    ingestForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById("doc-file");
        const adminKey = document.getElementById("admin-key").value;

        if (!fileInput.files.length) return;

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        ingestStatus.className = "feedback-msg";
        ingestStatus.textContent = "Indexing document into Pinecone...";

        try {
            const res = await fetch("/api/ingest", {
                method: "POST",
                headers: { "x-admin-key": adminKey },
                body: formData,
            });

            const result = await res.json();
            if (!res.ok) throw new Error(result.detail || "Upload failed");

            ingestStatus.className = "feedback-msg success";
            ingestStatus.textContent = `Indexed: ${result.file} (${result.chunks} chunks)`;
            fileInput.value = "";
        } catch (err) {
            ingestStatus.className = "feedback-msg error";
            ingestStatus.textContent = `Error: ${err.message}`;
        }
    });

    // 10. Clear Chat
    btnClear.addEventListener("click", () => {
        chatMessages.innerHTML = `
      <div class="message assistant-msg welcome-msg">
        <div class="avatar">N</div>
        <div class="message-content">
          <div class="message-body">
            <p>Conversation cleared. How can I help you today with company policies?</p>
          </div>
          <div class="meta-row">
            <span class="source-pill pill-system">System Ready</span>
          </div>
        </div>
      </div>
    `;
    });

    function escapeHtml(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
