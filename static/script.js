const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const input = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");
const clearBtn = document.getElementById("clear-btn");
const suggestions = document.getElementById("suggestions");

// the conversation so far (sent to the server so the LLM remembers it)
let history = [];

function scrollDown() {
  chat.scrollTop = chat.scrollHeight;
}

// Add a message bubble to the chat and return the message element
function addMessage(role, text, isError = false) {
  const message = document.createElement("div");
  message.className = "message " + role;

  const bubble = document.createElement("div");
  bubble.className = "bubble" + (isError ? " error" : "");
  bubble.textContent = text;

  message.appendChild(bubble);
  chat.appendChild(message);
  scrollDown();
  return message;
}

// Show what the agent did (each search and calculation)
function addSteps(message, steps) {
  if (!steps || steps.length === 0) return;

  const details = document.createElement("details");
  details.className = "sources";

  const summary = document.createElement("summary");
  summary.textContent = "Agent steps (" + steps.length + ")";
  details.appendChild(summary);

  steps.forEach(function (step, index) {
    const item = document.createElement("div");
    item.className = "source-item";

    const title = document.createElement("strong");
    title.textContent = (index + 1) + ". " + step.action + ": ";

    const text = document.createElement("span");
    text.textContent = step.input;

    item.appendChild(title);
    item.appendChild(text);
    details.appendChild(item);
  });

  message.appendChild(details);
}

// Show the chunks the answer was based on
function addSources(message, sources) {
  if (!sources || sources.length === 0) return;

  const details = document.createElement("details");
  details.className = "sources";

  const summary = document.createElement("summary");
  summary.textContent = "Sources (" + sources.length + ")";
  details.appendChild(summary);

  sources.forEach(function (s) {
    const item = document.createElement("div");
    item.className = "source-item";

    const title = document.createElement("strong");
    title.textContent = s.file + (s.page ? ", page " + s.page : "");

    const snippet = document.createElement("div");
    snippet.textContent = s.text + "...";

    item.appendChild(title);
    item.appendChild(snippet);
    details.appendChild(item);
  });

  message.appendChild(details);
}

function showTyping() {
  const message = document.createElement("div");
  message.className = "message bot";
  message.innerHTML = '<div class="bubble typing"><span></span><span></span><span></span></div>';
  chat.appendChild(message);
  scrollDown();
  return message;
}

async function sendQuestion(question) {
  suggestions.style.display = "none";
  addMessage("user", question);

  input.value = "";
  sendBtn.disabled = true;
  const typing = showTyping();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: history }),
    });
    const data = await response.json();
    typing.remove();

    if (!response.ok) {
      addMessage("bot", data.error || "Something went wrong.", true);
    } else {
      const message = addMessage("bot", data.answer);
      addSteps(message, data.steps);
      addSources(message, data.sources);
      history.push({ role: "user", content: question });
      history.push({ role: "assistant", content: data.answer });
    }
  } catch (error) {
    typing.remove();
    addMessage("bot", "Could not reach the server. Is app.py running?", true);
  }

  sendBtn.disabled = false;
  input.focus();
}

form.addEventListener("submit", function (event) {
  event.preventDefault();
  const question = input.value.trim();
  if (question) sendQuestion(question);
});

// Clicking a suggested question sends it
document.querySelectorAll(".chip").forEach(function (chip) {
  chip.addEventListener("click", function () {
    sendQuestion(chip.textContent);
  });
});

clearBtn.addEventListener("click", function () {
  history = [];
  location.reload();
});