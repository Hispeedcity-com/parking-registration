/* HispeedCity customer support chat widget */
(function () {
  const style = document.createElement('link');
  style.rel = 'stylesheet';
  style.href = 'ai-assistant.css';
  document.head.appendChild(style);

  const baseUrl = window.__API_BASE_URL__ || (
    window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? 'https://parking-registration-test-api.hostless.app/api'
      : 'https://parking-registration-test.hostless.site/api'
  );
  const apiUrl = `${baseUrl.replace(/\/$/, '')}/ai/chat`;
  let sessionId = sessionStorage.getItem('hscAssistantSession');
  if (!sessionId) {
    sessionId = `web_${Math.random().toString(36).slice(2)}_${Date.now()}`;
    sessionStorage.setItem('hscAssistantSession', sessionId);
  }

  document.addEventListener('DOMContentLoaded', init);

  function init() {
    if (document.getElementById('hsc-chat-launcher')) return;
    const launcher = document.createElement('button');
    launcher.id = 'hsc-chat-launcher';
    launcher.type = 'button';
    launcher.setAttribute('aria-label', 'Open HispeedCity AI Support');
    launcher.innerHTML = '<span aria-hidden="true">☏</span>';
    document.body.appendChild(launcher);

    const panel = document.createElement('section');
    panel.id = 'hsc-chat-container';
    panel.setAttribute('aria-label', 'HispeedCity AI Support');
    panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML = `
      <header class="hsc-chat-header">
        <div><strong>HispeedCity AI</strong><small><span class="hsc-status-dot"></span> Parking support</small></div>
        <button type="button" class="hsc-chat-close-btn" aria-label="Close chat">×</button>
      </header>
      <div class="hsc-chat-body" aria-live="polite"></div>
      <div class="hsc-quick-actions">
        <button type="button" class="hsc-quick-btn" data-query="Check my parking status">Check Status</button>
        <button type="button" class="hsc-quick-btn" data-query="My barrier won't open">Barrier Problem</button>
        <button type="button" class="hsc-quick-btn" data-query="How do I register for season parking?">Registration</button>
        <button type="button" class="hsc-quick-btn" data-query="How do I renew season parking?">Renewal</button>
      </div>
      <form class="hsc-chat-footer">
        <input type="text" class="hsc-chat-input" maxlength="2000" placeholder="Ask a question or enter a plate..." aria-label="Your message">
        <button type="submit" class="hsc-send-btn" aria-label="Send message">➤</button>
      </form>`;
    document.body.appendChild(panel);

    const body = panel.querySelector('.hsc-chat-body');
    const input = panel.querySelector('.hsc-chat-input');
    launcher.addEventListener('click', () => {
      const open = !panel.classList.contains('active');
      panel.classList.toggle('active', open);
      panel.setAttribute('aria-hidden', String(!open));
      if (open) input.focus();
    });
    panel.querySelector('.hsc-chat-close-btn').addEventListener('click', () => {
      panel.classList.remove('active');
      panel.setAttribute('aria-hidden', 'true');
    });
    panel.querySelector('.hsc-chat-footer').addEventListener('submit', event => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      input.value = '';
      ask(message);
    });
    panel.querySelectorAll('.hsc-quick-btn').forEach(button => {
      button.addEventListener('click', () => ask(button.dataset.query));
    });
    appendMessage('Hello! Welcome to HispeedCity support. Ask about parking, registration, renewals, or barrier access.', 'bot');

    async function ask(message) {
      appendMessage(message, 'user');
      const typing = appendMessage('Thinking…', 'bot', true);
      try {
        const response = await fetch(apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message, session_id: sessionId }),
        });
        const data = await response.json();
        typing.remove();
        if (!response.ok) throw new Error(data.detail || 'Assistant is temporarily unavailable.');
        appendMessage(data.answer || 'Sorry, I could not find an answer.', 'bot');
      } catch (error) {
        typing.remove();
        appendMessage(error.message || 'Connection issue. Please try again later.', 'bot');
      }
    }

    function appendMessage(text, role, isTyping = false) {
      const wrap = document.createElement('div');
      wrap.className = `hsc-msg-wrap hsc-msg-${role}`;
      if (isTyping) wrap.classList.add('hsc-typing');
      const bubble = document.createElement('div');
      bubble.className = 'hsc-bubble';
      bubble.textContent = text;
      wrap.appendChild(bubble);
      body.appendChild(wrap);
      body.scrollTop = body.scrollHeight;
      return wrap;
    }
  }
})();
