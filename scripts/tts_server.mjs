#!/usr/bin/env node
// Paste-and-listen: paste a Claude/Codex response, Deepgram reads it aloud.
//   node scripts/tts_server.mjs   -> http://localhost:8899
// No dependencies. Key is read from env or .env; it never reaches the browser.
//
// Deepgram's first byte lands in ~0.2s, so /audio just pipes its stream straight
// through to the <audio> element. Playback starts immediately; no buffering step.

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { Readable } from 'node:stream';

const PORT = Number(process.env.TTS_PORT || 8899);

function apiKey() {
  if (process.env.DEEPGRAM_API_KEY) return process.env.DEEPGRAM_API_KEY;
  try {
    const m = readFileSync(new URL('../.env', import.meta.url), 'utf8')
      .match(/^DEEPGRAM_API_KEY=(.*)$/m);
    if (m) return m[1].trim().replace(/^["']|["']$/g, '');
  } catch {}
  return null;
}

// Markdown -> speakable prose. Code blocks are noise when listening.
function speakable(md, { skipCode = true } = {}) {
  let t = md.replace(/\r/g, '');
  t = t.replace(/```[\s\S]*?```/g, skipCode ? ' (code block) ' : ' $& ');
  t = t.replace(/`([^`]+)`/g, '$1');
  t = t.replace(/^\s{0,3}#{1,6}\s*/gm, '');
  t = t.replace(/^\s*[-*+]\s+/gm, '');
  t = t.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/(?<!\*)\*([^*]+)\*/g, '$1');
  t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  t = t.replace(/^\s*\|.*\|\s*$/gm, ' ');
  t = t.replace(/^\s*[-=_]{3,}\s*$/gm, ' ');
  t = t.replace(/https?:\/\/\S+/g, ' link ');
  return t.replace(/\n{2,}/g, '\n').replace(/[ \t]{2,}/g, ' ').trim();
}

// Deepgram caps request size; split on sentence bounds, then stream them back to back.
function chunk(text, max = 700) {
  const out = [];
  let buf = '';
  for (const part of text.split(/(?<=[.!?:\n])\s+/)) {
    if ((buf + ' ' + part).length > max) { if (buf) out.push(buf); buf = part; }
    else buf = buf ? buf + ' ' + part : part;
  }
  if (buf.trim()) out.push(buf.trim());
  return out.filter(Boolean);
}

// The browser can't POST an <audio> src, so text is staged here and fetched by id.
const staged = new Map();

const HTML = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Read it to me</title><style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#0e0f11;color:#e8e6e3;font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;
     display:flex;flex-direction:column;height:100dvh}
header{padding:12px 18px;border-bottom:1px solid #26282c;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:14px;margin:0 auto 0 0;font-weight:600;letter-spacing:.02em}
select,label{font:inherit;font-size:13px;color:#b9b6b1}
select{background:#191b1f;border:1px solid #33363c;border-radius:6px;padding:5px 8px;color:#e8e6e3}
textarea{flex:1;width:100%;resize:none;background:#131417;color:#e8e6e3;border:none;
  padding:18px;font:14px/1.6 ui-monospace,SFMono-Regular,monospace;outline:none}
#player{border-top:1px solid #26282c;padding:14px 18px 18px;display:flex;flex-direction:column;gap:12px}
#scrub{width:100%;-webkit-appearance:none;appearance:none;height:6px;border-radius:3px;
  background:#2a2d33;outline:none;cursor:pointer}
#scrub::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:#e8e6e3}
#scrub::-moz-range-thumb{width:14px;height:14px;border:none;border-radius:50%;background:#e8e6e3}
#scrub:disabled{opacity:.4;cursor:default}
.row{display:flex;gap:10px;align-items:center}
button{font:inherit;font-weight:600;border:none;border-radius:8px;padding:9px 14px;cursor:pointer;
  background:#22252a;color:#e8e6e3}
button.primary{background:#e8e6e3;color:#0e0f11;min-width:104px}
button:disabled{opacity:.4;cursor:default}
#time{font:12px ui-monospace,monospace;color:#8d8a86;margin-left:auto}
#status{font-size:13px;color:#8d8a86}
kbd{background:#22252a;border-radius:4px;padding:1px 5px;font-size:11px}
</style></head><body>
<header>
  <h1>Read it to me</h1>
  <select id="voice">
    <option value="aura-2-thalia-en">Thalia (f, clear)</option>
    <option value="aura-2-andromeda-en">Andromeda (f, warm)</option>
    <option value="aura-2-apollo-en">Apollo (m, calm)</option>
    <option value="aura-2-orion-en">Orion (m, deep)</option>
    <option value="aura-2-arcas-en">Arcas (m, natural)</option>
  </select>
  <label><input type="checkbox" id="skipcode" checked> skip code blocks</label>
</header>
<div id="msgs" style="padding:8px 18px;border-bottom:1px solid #26282c;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
  <span style="font-size:12px;color:#8d8a86">Claude's messages:</span>
  <span id="msglist" style="display:flex;gap:8px;flex-wrap:wrap"></span>
  <button id="refresh" style="padding:4px 10px;font-size:12px">refresh</button>
</div>
<textarea id="text" autofocus placeholder="Click a message above, or paste anything here, then hit Cmd/Ctrl+Enter…"></textarea>
<div id="player">
  <input id="scrub" type="range" min="0" max="1000" value="0" disabled>
  <div class="row">
    <button id="load" class="primary">Read it</button>
    <button id="back" disabled>&#8630; 15s</button>
    <button id="play" disabled>Play</button>
    <button id="fwd" disabled>15s &#8631;</button>
    <select id="rate">
      <option value="1">1.0x</option><option value="1.25">1.25x</option>
      <option value="1.5" selected>1.5x</option><option value="1.75">1.75x</option>
      <option value="2">2.0x</option><option value="2.5">2.5x</option>
    </select>
    <span id="time">0:00 / 0:00</span>
  </div>
  <div id="status">idle &nbsp;<kbd>⌘↵</kbd> read &nbsp;<kbd>space</kbd> play/pause &nbsp;<kbd>←/→</kbd> 15s</div>
</div>
<script>
const $ = id => document.getElementById(id);
async function loadMsgs(){
  const files = await (await fetch('/messages')).json();
  const box = $('msglist'); box.innerHTML = '';
  for (const f of files.slice(0, 12)) {
    const b = document.createElement('button');
    b.textContent = f.replace(/\.md$/, '').replace(/^\d{8}-\d{4}-/, '');
    b.style.cssText = 'padding:4px 10px;font-size:12px';
    b.onclick = async () => { $('text').value = await (await fetch('/message?f=' + encodeURIComponent(f))).text(); $('load').click(); };
    box.appendChild(b);
  }
}
$('refresh')?.addEventListener?.('click', loadMsgs);
loadMsgs();
const audio = new Audio();
let seeking = false, estimate = 0;

const fmt = s => (!isFinite(s) || s < 0) ? '0:00'
  : Math.floor(s/60) + ':' + String(Math.floor(s%60)).padStart(2,'0');
const rate = () => audio.playbackRate || 1;
// Until the stream finishes, duration is Infinity — fall back to a chars-per-second guess.
const total = () => isFinite(audio.duration) ? audio.duration : estimate;

function updateTime(){
  $('time').textContent = fmt(audio.currentTime/rate()) + ' / ' + fmt(total()/rate())
    + (isFinite(audio.duration) ? '' : ' (est)');
}

function read(){
  const text = $('text').value;
  if (!text.trim()) return;
  estimate = text.length / 14.5;            // ~14.5 spoken chars per second at 1x
  audio.playbackRate = Number($('rate').value);
  audio.src = '/audio?' + new URLSearchParams({ voice: $('voice').value, skip: $('skipcode').checked ? '1':'0' })
    + '&_=' + performance.now();
  // The text goes up in a POST that /audio waits for, keyed by the same session.
  fetch('/stage', {method:'POST', body: text});
  audio.play().catch(() => setStatus('press Play'));
  ['play','back','fwd','scrub'].forEach(id => $(id).disabled = false);
}

const setStatus = s => $('status').textContent = s;
const toggle = () => { if (audio.src) audio.paused ? audio.play() : audio.pause() };
const nudge = d => { if (audio.src) audio.currentTime = Math.max(0, audio.currentTime + d) };

audio.onplay  = () => { $('play').textContent = 'Pause'; setStatus('playing') };
audio.onpause = () => { $('play').textContent = 'Play'; if(!audio.ended) setStatus('paused') };
audio.onended = () => setStatus('done');
audio.onerror = () => setStatus('error — check the server log');
audio.ondurationchange = updateTime;
audio.ontimeupdate = () => {
  updateTime();
  if (!seeking && total()) $('scrub').value = Math.min(1000, (audio.currentTime/total())*1000);
};

$('load').onclick = read;
$('play').onclick = toggle;
$('back').onclick = () => nudge(-15);
$('fwd').onclick  = () => nudge(15);
$('rate').onchange = () => { audio.playbackRate = Number($('rate').value); updateTime() };
$('scrub').oninput = e => { seeking = true; if (total()) audio.currentTime = (e.target.value/1000)*total() };
$('scrub').onchange = () => seeking = false;

document.addEventListener('keydown', e => {
  if ((e.metaKey||e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); return read() }
  if (e.target.tagName === 'TEXTAREA') return;   // don't hijack typing
  if (e.key === ' ') { e.preventDefault(); toggle() }
  if (e.key === 'ArrowLeft') nudge(-15);
  if (e.key === 'ArrowRight') nudge(15);
});
</script></body></html>`;

function body(req) {
  return new Promise((res, rej) => {
    let b = '';
    req.on('data', d => { b += d; if (b.length > 5e6) req.destroy(); });
    req.on('end', () => res(b));
    req.on('error', rej);
  });
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  try {
    if (url.pathname === '/') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      return res.end(HTML);
    }

    if (url.pathname === '/messages') {
      // Claude drops explanations into data/tts_messages/*.md; newest first.
      const dir = new URL('../data/tts_messages/', import.meta.url);
      let files = [];
      try { if (existsSync(dir)) files = readdirSync(dir).filter(f => f.endsWith('.md')).sort().reverse(); } catch {}
      res.writeHead(200, {'content-type': 'application/json'});
      res.end(JSON.stringify(files));
      return;
    }
    if (url.pathname === '/message') {
      const f = url.searchParams.get('f') || '';
      if (!/^[A-Za-z0-9._-]+\.md$/.test(f)) { res.writeHead(400); res.end('bad'); return; }
      try {
        const txt = readFileSync(new URL('../data/tts_messages/' + f, import.meta.url), 'utf8');
        res.writeHead(200, {'content-type': 'text/plain; charset=utf-8'});
        res.end(txt);
      } catch { res.writeHead(404); res.end('not found'); }
      return;
    }
    if (url.pathname === '/stage' && req.method === 'POST') {
      const text = await body(req);
      staged.set('current', text);
      staged.get('waiter')?.(text);
      res.writeHead(204);
      return res.end();
    }

    if (url.pathname === '/audio') {
      const key = apiKey();
      if (!key) { res.writeHead(500); return res.end('DEEPGRAM_API_KEY not set'); }

      // The <audio> GET can beat the POST; wait briefly for the text to arrive.
      let text = staged.get('current');
      if (!text) {
        text = await Promise.race([
          new Promise(r => staged.set('waiter', r)),
          new Promise(r => setTimeout(() => r(''), 3000)),
        ]);
      }
      staged.delete('current');
      staged.delete('waiter');

      const model = /^aura-2?-[a-z]+-en$/.test(url.searchParams.get('voice') || '')
        ? url.searchParams.get('voice') : 'aura-2-thalia-en';
      const parts = chunk(speakable(text, { skipCode: url.searchParams.get('skip') !== '0' }));
      if (!parts.length) { res.writeHead(400); return res.end('nothing to say'); }

      res.writeHead(200, { 'content-type': 'audio/mpeg', 'cache-control': 'no-store' });
      const t0 = Date.now();

      // Deepgram generates ~1.6x realtime, which is too thin a margin at 1.5x playback.
      // Keep a few chunks in flight ahead of the one being written so audio never stalls;
      // bodies are still consumed in order, so the mp3 stream stays correct.
      const LOOKAHEAD = 3;
      const say = part => fetch(`https://api.deepgram.com/v1/speak?model=${model}&encoding=mp3`, {
        method: 'POST',
        headers: { Authorization: `Token ${key}`, 'content-type': 'application/json' },
        body: JSON.stringify({ text: part }),
      });

      const inflight = parts.slice(0, LOOKAHEAD).map(say);
      for (let i = 0; i < parts.length; i++) {
        if (i + LOOKAHEAD < parts.length) inflight.push(say(parts[i + LOOKAHEAD]));
        const dg = await inflight[i];
        if (!dg.ok) { console.error('deepgram', dg.status, await dg.text()); break; }
        // Pipe as it arrives — this is what makes playback start in ~0.4s.
        for await (const buf of Readable.fromWeb(dg.body)) {
          if (!res.write(buf)) await new Promise(r => res.once('drain', r));
        }
      }
      console.log(`streamed ${parts.length} chunk(s) in ${Date.now() - t0}ms`);
      return res.end();
    }

    res.writeHead(404);
    res.end('not found');
  } catch (e) {
    console.error(e);
    if (!res.headersSent) res.writeHead(500);
    res.end(String(e && e.message || e));
  }
});

server.listen(PORT, () => {
  console.log(`TTS ready  ->  http://localhost:${PORT}`);
  if (!apiKey()) console.log('WARNING: DEEPGRAM_API_KEY not found in env or .env');
});
