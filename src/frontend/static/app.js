const $ = (s) => document.querySelector(s);
const API = "http://127.0.0.1:8000";
let currentId = null;
let streaming = false;

// fetch Wrapper for API calls
async function api(path, opts) {
    const res = await fetch(API + path, opts);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res;
}

async function loadSessions() {
    const list = await (await api('/api/sessions')).json();
    const box = $('#sessions');
    box.replaceChildren();
    for (const s of list) {
        const row = document.createElement('div');
        row.className = 'session' + (s.id === currentId ? ' active' : '');

        const title = document.createElement('span');
        title.className = 'title';
        title.textContent = s.title;

        const del = document.createElement('button');
        del.className = 'del';
        del.textContent = '×';
        del.title = 'Delete chat';
        del.onclick = async (e) => {
            e.stopPropagation();
            if (!confirm('Delete this chat?')) return;
            await api('/api/sessions/' + s.id, { method: 'DELETE' });
            if (currentId === s.id) newChat();
            loadSessions();
        };

        row.onclick = () => openSession(s.id);
        row.append(title, del);
        box.append(row);
    }
}

async function openSession(id) {
    if (streaming) return;
    currentId = id;
    const msgs = await (await api(`/api/sessions/${id}/messages`)).json();
    $('#thread').replaceChildren();
    for (const m of msgs) addMessage(m.role, m.content);
    scrollDown();
    $('#sidebar').classList.remove('open');
    loadSessions();
}

function newChat() {
    if (streaming) return;
    currentId = null;
    showEmpty();
    $('#sidebar').classList.remove('open');
    loadSessions();
    $('#input').focus();
}

function showEmpty() {
    const t = $('#thread');
    t.replaceChildren();
    const e = document.createElement('div');
    e.id = 'empty';
    e.textContent = 'What do you want to ask?';
    t.append(e);
}

function addMessage(role, text) {
    $('#empty')?.remove();
    const msg = document.createElement('div');
    msg.className = 'msg ' + role;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    msg.append(bubble);
    $('#thread').append(msg);
    return bubble;
}

function scrollDown() {
    const m = $('#messages');
    m.scrollTop = m.scrollHeight;
}

function setBusy(busy) {
    streaming = busy;
    $('#send').disabled = busy;
}

function handleLine(obj, bubble) {
    if (obj.t !== undefined) {
    bubble.textContent += obj.t;
    scrollDown();
    } else if (obj.sources) {
    if (obj.sources.length) {
        const s = document.createElement('div');
        s.className = 'sources';
        s.textContent = 'Sources: ' + obj.sources.join(', ');
        bubble.parentElement.append(s);
    }
    } else if (obj.error) {
    bubble.textContent += (bubble.textContent ? '\n\n' : '') + 'Error: ' + obj.error;
    }
}

async function send() {
    const input = $('#input');
    const text = input.value.trim();
    if (!text || streaming) return;

    setBusy(true);
    input.value = '';
    autosize();
    addMessage('user', text);
    const bot = addMessage('assistant', '');
    bot.classList.add('cursor');
    scrollDown();

    try {
    if (!currentId) {
        const r = await api('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: text.slice(0, 50) }),
        });
        currentId = (await r.json()).id;
    }

    const res = await api(`/api/sessions/${currentId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf('\n')) >= 0) {
            const line = buf.slice(0, i);
            buf = buf.slice(i + 1);
            if (line) handleLine(JSON.parse(line), bot);
        }
    }
    } catch (e) {
        bot.textContent = 'Error: ' + e.message;
    } finally {
        bot.classList.remove('cursor');
        setBusy(false);
        loadSessions();
        input.focus();
    }
}

function autosize() {
    const el = $('#input');
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
}
 
$('#input').addEventListener('input', autosize);
$('#input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        send();
    }
});

$('#send').onclick = send;
$('#new-chat').onclick = newChat;
$('#menu').onclick = () => $('#sidebar').classList.toggle('open');
 
showEmpty();
loadSessions();