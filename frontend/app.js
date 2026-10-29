'use strict';

// The original REST / WebSocket contract and evaluation threshold are preserved.
const $ = selector => document.querySelector(selector);
const app = $('#app');
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const THRESHOLD = 0.14;
// Display-only snapshot of template hand sides. Regenerate when lesson templates change.
const LESSON_HANDS = {
  "greetings": {
    "deaf": [
      "Right"
    ],
    "fine or happy": [
      "Left",
      "Right"
    ],
    "finger spelling name": [
      "Left",
      "Right"
    ],
    "fun": [
      "Left",
      "Right"
    ],
    "good luck": [
      "Left"
    ],
    "hard of hearing": [
      "Left",
      "Right"
    ],
    "hearing": [
      "Right"
    ],
    "hello (friend)": [
      "Left"
    ],
    "hello": [
      "Left",
      "Right"
    ],
    "learn": [
      "Left",
      "Right"
    ],
    "name and surname": [
      "Right"
    ],
    "no": [
      "Left",
      "Right"
    ],
    "not happy": [
      "Left",
      "Right"
    ],
    "remember": [
      "Left",
      "Right"
    ],
    "sick": [
      "Left",
      "Right"
    ],
    "sign language": [
      "Left",
      "Right"
    ],
    "sign name": [
      "Left",
      "Right"
    ],
    "sorry (with respect)": [
      "Left",
      "Right"
    ],
    "sorry": [
      "Left",
      "Right"
    ],
    "surname": [
      "Left",
      "Right"
    ],
    "thank you": [
      "Left",
      "Right"
    ],
    "you_re welcome": [
      "Right"
    ]
  },
  "numbers": {
    "eight-hundred": [
      "Right"
    ],
    "eight": [
      "Right"
    ],
    "eighteen": [
      "Left"
    ],
    "eighty": [
      "Right"
    ],
    "eleven": [
      "Right"
    ],
    "fifteen": [
      "Left"
    ],
    "fifty": [
      "Left"
    ],
    "five-hundred": [
      "Right"
    ],
    "four-hundred": [
      "Left",
      "Right"
    ],
    "fourteen": [
      "Right"
    ],
    "fourty": [
      "Left"
    ],
    "nine-hundred": [
      "Right"
    ],
    "nine": [
      "Right"
    ],
    "nineteen": [
      "Left"
    ],
    "ninety": [
      "Right"
    ],
    "one hundred thousand": [
      "Right"
    ],
    "one million": [
      "Left"
    ],
    "one thousand": [
      "Left"
    ],
    "one-hundred": [
      "Left",
      "Right"
    ],
    "one": [
      "Left"
    ],
    "seven-hundred": [
      "Left",
      "Right"
    ],
    "seven": [
      "Left"
    ],
    "seventeen": [
      "Left"
    ],
    "seventy": [
      "Right"
    ],
    "six": [
      "Right"
    ],
    "sixteen": [
      "Left"
    ],
    "sixty": [
      "Right"
    ],
    "ten thousand": [
      "Left"
    ],
    "thirteen": [
      "Left"
    ],
    "thirty": [
      "Right"
    ],
    "three-hundred": [
      "Right"
    ],
    "twelve": [
      "Left"
    ],
    "twenty": [
      "Left"
    ],
    "two": [
      "Right"
    ]
  },
  "times": {
    "afternoon": [
      "Left",
      "Right"
    ],
    "evening": [
      "Left",
      "Right"
    ],
    "midday": [
      "Left",
      "Right"
    ],
    "midnight": [
      "Right"
    ],
    "morning": [
      "Left",
      "Right"
    ],
    "night time dark": [
      "Right"
    ],
    "time": [
      "Left",
      "Right"
    ],
    "twilight": [
      "Right"
    ]
  }
};
function lessonHandsLabel(chapter, word) {
  const sides = LESSON_HANDS[chapter]?.[word];
  if (!Array.isArray(sides) || !sides.length) return 'ยังไม่มีข้อมูลมือที่ใช้';
  return sides.length === 2 ? 'ทั้งสองมือ' : sides[0] === 'Left' ? 'มือซ้าย' : 'มือขวา';
}
const lessonHandsNotice = () => `<p class="tip">มือที่ใช้: <strong>${esc(lessonHandsLabel(S.chapter, S.word))}</strong></p>`;

const CONN = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
const S = {chapter:null, chapterName:'', word:null, wordName:'', mirrorTeacher:true};
const chapterDesign = {
  greetings: {icon:'chat', description:'เริ่มบทสนทนาด้วยภาษามือ'},
  numbers: {icon:'hash', description:'ตัวเลขที่ใช้ในชีวิตประจำวัน'},
  times: {icon:'clock', description:'สื่อสารเรื่องเวลาได้อย่างมั่นใจ'}
};
// Local SVG icons avoid an extra library download.
const paths = {
  hand:'<path d="M8 13V6a2 2 0 0 1 4 0v6M12 11V4a2 2 0 0 1 4 0v9M16 11V7a2 2 0 0 1 4 0v8c0 4-3 7-7 7h-1c-2 0-4-1-5-3l-4-5a2 2 0 0 1 3-3l2 2Z"/>',
  chat:'<path d="M21 11a9 9 0 0 1-9 9 10 10 0 0 1-4-1l-5 2 1-5a9 9 0 1 1 17-5Z"/>',
  hash:'<path d="m10 3-2 18M16 3l-2 18M4 9h16M3 15h16"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5h4"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  diagonal:'<path d="M6 18 18 6M6 6h12v12"/>',
  back:'<path d="M20 12H4m6-6-6 6 6 6"/>',
  mail:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z"/>',
  camera:'<rect x="3" y="6" width="14" height="13" rx="3"/><path d="m17 10 4-3v12l-4-3"/>',
  tip:'<path d="M9 18h6m-6 3h6M8 14a6 6 0 1 1 8 0c-1 1-1 2-1 2H9s0-1-1-2"/>',
  repeat:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
  record:'<circle cx="12" cy="12" r="7"/>',
  stop:'<rect x="5" y="5" width="14" height="14" rx="2"/>'
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.hand}</svg>`;
let cam = null;
let viewId = 0;
let currentView = 'home';
let recording = false;
let evaluating = false;
let teacherReady = false;

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

// Navigation invalidates outstanding requests and closes the previous session.
function go(view, ...args) {
  if ((view === 'hand' || view === 'practice') && !S.word) view = 'words';
  if (cam) { cam.stop(); cam = null; }
  const teacher = $('#tv');
  if (teacher) { teacher.oncanplay = null; teacher.onerror = null; teacher.pause(); }
  recording = false;
  evaluating = false;
  currentView = view;
  const id = ++viewId;
  document.querySelectorAll('[data-nav]').forEach(button => {
    if (button.dataset.nav === (view === 'home' ? 'home' : 'words')) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  window.scrollTo(0, 0);
  views[view](id, ...args);
  app.focus({preventScroll:true});
}
function steps(active) {
  return `<ol class="stepper" aria-label="ขั้นตอนการเรียน">${['เลือกบทเรียน','ตรวจสอบกล้อง','ฝึกท่าทาง','ดูผลลัพธ์'].map((label,i) => `<li ${i === active ? 'aria-current="step"' : ''}><b>${i+1}</b><span>${label}</span></li>`).join('')}</ol>`;
}
function breadcrumb() {
  return `<div class="crumb"><button class="text-button" data-go="words">${icon('back')} ${esc(S.chapterName)}</button><span>/</span><span>${esc(S.wordName)}</span></div>`;
}
function loading() { return '<p class="notice" role="status">กำลังโหลดบทเรียน…</p>'; }
function loadError(retry) {
  return `<div class="notice" role="alert"><p>เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาตรวจสอบว่า backend กำลังทำงาน</p><button class="sec" data-go="${retry}">${icon('repeat')} ลองอีกครั้ง</button></div>`;
}

/* Camera and WebSocket. JPEG input remains unmirrored; the server flips it. */
class Cam {
  constructor(video, overlay, onHands, onMsg, onState) {
    Object.assign(this, {v:video, o:overlay, onHands, onMsg, onState, n:0, t:0, fr:[], dead:false, ready:false});
    this.work = document.createElement('canvas');
  }
  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}}});
    if (this.dead) { this.stream.getTracks().forEach(track => track.stop()); return; }
    this.v.srcObject = this.stream;
    await this.v.play();
    if (this.dead) return;
    this.resize();
    this.v.onresize = () => this.resize();
    this.ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/session');
    this.ws.onopen = () => {
      if (this.dead) return;
      if (this.cfg) this.send(this.cfg);
      this.loop();
    };
    this.ws.onmessage = event => {
      if (this.dead) return;
      const message = JSON.parse(event.data);
      if (message.type === 'hands') {
        this.n = Math.max(0, this.n - 1);
        if (!this.ready) { this.ready = true; clearTimeout(this.timeout); this.onState('ready'); }
        this.draw(message.hands);
        this.stat(message);
        this.onHands(message);
      } else if (this.onMsg) this.onMsg(message);
    };
    this.ws.onerror = () => this.fail();
    this.ws.onclose = () => this.fail();
    this.timeout = setTimeout(() => { if (!this.ready) this.fail(); }, 15000);
    this.stream.getVideoTracks().forEach(track => { track.onended = () => this.fail('กล้องหยุดทำงาน กรุณาเชื่อมต่อกล้องแล้วลองอีกครั้ง'); });
  }
  resize() {
    const ratio = this.v.videoWidth / this.v.videoHeight;
    if (!Number.isFinite(ratio) || ratio <= 0) return;
    // Video and landmarks share the same fitted rectangle inside the 4:3 stage.
    const surface = this.v.parentElement;
    surface.style.width = ratio >= 4/3 ? '100%' : `${ratio / (4/3) * 100}%`;
    surface.style.height = ratio >= 4/3 ? `${(4/3) / ratio * 100}%` : '100%';
  }
  fail(message = 'การเชื่อมต่อระบบตรวจจับมือขัดข้อง กรุณาตรวจสอบ backend แล้วลองอีกครั้ง') {
    if (this.dead) return;
    this.stop();
    this.onState('error', message);
  }
  loop() {
    if (this.dead) return;
    const now = performance.now();
    if (this.n > 0 && now - this.t > 2000) this.n = 0;
    if (this.n < 2 && this.ws.readyState === WebSocket.OPEN && this.v.videoWidth) {
      this.work.width = 640;
      this.work.height = Math.round(640 * this.v.videoHeight / this.v.videoWidth);
      this.work.getContext('2d').drawImage(this.v, 0, 0, this.work.width, this.work.height);
      this.n++;
      this.t = now;
      this.work.toBlob(blob => {
        if (blob && !this.dead && this.ws.readyState === WebSocket.OPEN) this.ws.send(blob);
      }, 'image/jpeg', .85);
    }
    this.raf = requestAnimationFrame(() => this.loop());
  }
  stat(message) {
    const now = performance.now();
    this.fr.push(now);
    while (this.fr.length && now - this.fr[0] > 1000) this.fr.shift();
    const el = $('#fps');
    if (el) el.textContent = `${message.ms} ms · ${this.fr.length} fps`;
  }
  send(message) {
    if (this.dead || this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(message));
    return true;
  }
  draw(hands) {
    const c = this.o, w = c.width = this.v.videoWidth, h = c.height = this.v.videoHeight, g = c.getContext('2d');
    g.clearRect(0,0,w,h);
    g.lineWidth = 3;
    for (const hand of hands) {
      const color = hand.label === 'Right' ? '#38e07b' : '#ffc53d';
      const points = hand.landmarks.map(p => [p[0]*w,p[1]*h]);
      g.strokeStyle = color;
      g.fillStyle = '#fff';
      for (const [a,b] of CONN) { g.beginPath(); g.moveTo(...points[a]); g.lineTo(...points[b]); g.stroke(); }
      for (const p of points) { g.beginPath(); g.arc(p[0],p[1],4,0,7); g.fill(); }
      g.fillStyle = color;
      g.font = '500 22px Prompt, sans-serif';
      g.fillText(hand.label === 'Right' ? 'มือขวา' : 'มือซ้าย',points[0][0]-30,points[0][1]+34);
    }
  }
  stop() {
    this.dead = true;
    this.ready = false;
    clearTimeout(this.timeout);
    cancelAnimationFrame(this.raf);
    if (this.ws) this.ws.close();
    if (this.stream) this.stream.getTracks().forEach(track => track.stop());
    this.v.onresize = null;
    this.v.srcObject = null;
  }
}

function syncPracticeButtons() {
  if (!$('#start')) return;
  const ready = Boolean(cam?.ready && !cam.dead && teacherReady);
  $('#start').disabled = !ready || recording || evaluating;
  $('#stop').disabled = !ready || !recording || evaluating;
}
async function openCam(onHands, onMsg, cfg) {
  const id = viewId;
  const session = new Cam($('#cam'), $('#ov'), onHands, onMsg, (state, message) => {
    if (id !== viewId) return;
    const status = $('#camStatus');
    status.className = `status ${state}`;
    status.textContent = state === 'ready' ? 'กล้องและระบบพร้อม' : 'การเชื่อมต่อขัดข้อง';
    $('#cameraPlaceholder').hidden = state === 'ready';
    if (state === 'error') {
      recording = false;
      evaluating = false;
      $('#cameraPlaceholder').innerHTML = `${icon('camera')}<span>กล้องยังไม่พร้อมใช้งาน</span>`;
      $('#camErr').innerHTML = `<p class="warn" role="alert">${esc(message)}</p><button class="sec" data-go="${currentView}">ลองเปิดกล้องอีกครั้ง</button>`;
      if ($('#rec')) $('#rec').hidden = true;
      if ($('#msg')) $('#msg').textContent = 'การฝึกหยุดลง กรุณาเชื่อมต่อใหม่แล้วบันทึกอีกครั้ง';
      if ($('#ok')) $('#ok').disabled = true;
    }
    syncPracticeButtons();
  });
  session.cfg = cfg;
  cam = session;
  try { await session.start(); }
  catch (error) {
    if (id !== viewId) { session.stop(); return; }
    const message = error.name === 'NotAllowedError'
      ? 'ไม่ได้รับอนุญาตใช้กล้อง กรุณาอนุญาตกล้องในเบราว์เซอร์แล้วลองอีกครั้ง'
      : 'เปิดกล้องไม่ได้ กรุณาตรวจสอบว่ามีกล้องและไม่มีโปรแกรมอื่นใช้งานอยู่';
    session.fail(message);
  }
}
const stage = () => `<div class="stage"><div class="camera-surface"><video id="cam" class="mir" muted playsinline></video><canvas id="ov" aria-hidden="true"></canvas></div><div class="stage-placeholder" id="cameraPlaceholder">${icon('camera')}<span>กำลังเตรียมกล้องและระบบตรวจจับมือ…</span></div><span class="badge" id="rec" hidden>● กำลังบันทึก</span></div><div id="camErr" class="message"></div><details class="diagnostics"><summary>รายละเอียดการเชื่อมต่อ</summary><span id="fps">กำลังเชื่อมต่อ…</span></details>`;
const sessionConfig = () => ({type:'config', chapter:S.chapter, word:S.word});

/* Screens use real API data, never the preview's mock scores or vocabulary. */
const views = {
  async home(id) {
    app.innerHTML = `<div class="page">
      <section class="hero"><div><div class="eyebrow">A LITTLE PRACTICE. A NEW CONNECTION.</div>
        <h1>ให้ทุกท่าทาง<br><span>เชื่อมเราเข้าหากัน</span></h1>
        <p>เรียนภาษามือในจังหวะของคุณ ดูตัวอย่าง ฝึกตาม แล้วเรียนรู้จากคำแนะนำของ AI</p>
        <div class="row"><button class="pri" data-go="words">เริ่มเรียนภาษามือ ${icon('arrow')}</button></div></div>
        <div class="hero-art" aria-hidden="true"><div class="orbit"></div><div class="hero-hand">${icon('hand')}</div><div class="float-label top">${icon('spark')} ฝึกทีละนิด เข้าใจมากขึ้น</div><div class="float-label bottom">${icon('camera')} เรียนรู้ผ่านการลงมือทำ</div></div>
      </section>
      <div class="section-heading"><h2>วันนี้อยากเรียนเรื่องอะไร?</h2><span class="muted small">เลือกหมวดที่สนใจ แล้วเริ่มได้เลย</span></div>
      <div class="grid chapter-grid" id="chGrid" aria-live="polite">${loading()}</div>
      <section aria-labelledby="how-title"><div class="section-heading"><h2 id="how-title">วิธีใช้งาน 4 ขั้นตอน</h2></div>
        <ol class="steps">${[['เลือกบทเรียน','เลือกหมวดหมู่และคำศัพท์ที่ต้องการฝึก'],['เปิดใช้งานกล้อง','ระบบตรวจสอบมือซ้าย/ขวาของคุณ'],['แสดงท่าทาง','ทำท่าตามคลิปผู้สอนหน้ากล้อง'],['พิจารณาผลลัพธ์','ดูคะแนนและจุดที่ควรปรับ']].map(([title,text],i) => `<li><div class="step-title"><b aria-hidden="true">${i+1}</b><h3>${title}</h3></div><p>${text}</p></li>`).join('')}</ol>
      </section></div>`;
    try {
      const chapters = await api('/api/chapters');
      if (id !== viewId) return;
      $('#chGrid').innerHTML = chapters.length ? chapters.map(c => {
        const design = chapterDesign[c.id] || {icon:'hand',description:c.en};
        return `<button class="card" data-chapter="${esc(c.id)}" data-name="${esc(c.th)}" ${c.count ? '' : 'disabled'}><span class="symbol">${icon(design.icon)}</span><strong>${esc(c.th)}</strong><small>${esc(design.description)}</small><small>${c.count} คำศัพท์</small><span class="card-link">สำรวจบทเรียน ${icon('diagonal')}</span></button>`;
      }).join('') : '<p class="notice">ยังไม่มีบทเรียน</p>';
    } catch { if (id === viewId) $('#chGrid').innerHTML = loadError('home'); }
  },

  async words(id) {
    app.innerHTML = `<section class="page">${steps(0)}<div id="lessonArea">${loading()}</div></section>`;
    try {
      const chapters = await api('/api/chapters');
      if (id !== viewId) return;
      const selected = chapters.find(c => c.id === S.chapter) || chapters.find(c => c.count) || chapters[0];
      if (!selected) { $('#lessonArea').innerHTML = '<p class="notice">ยังไม่มีบทเรียน</p>'; return; }
      if (S.chapter !== selected.id) { S.word = null; S.wordName = ''; }
      S.chapter = selected.id;
      S.chapterName = selected.th;
      $('#lessonArea').innerHTML = `<div class="lesson-layout">
        <aside class="sidebar"><h2>บทเรียนทั้งหมด</h2><p>เลือกหมวดที่อยากฝึก</p>
          <nav class="category-nav" aria-label="หมวดบทเรียน">${chapters.map(c => `<button data-chapter="${esc(c.id)}" data-name="${esc(c.th)}" aria-current="${c.id === S.chapter}" ${c.count ? '' : 'disabled'}>${icon(chapterDesign[c.id]?.icon || 'hand')}<span>${esc(c.th)}</span><span class="arrow">›</span></button>`).join('')}</nav>
          <div class="side-tip">เรียนรู้ทีละคำ<br>ฝึกซ้ำได้ในจังหวะของคุณ</div>
        </aside>
        <div class="lesson-content"><div class="crumb"><button class="text-button" data-go="home">${icon('back')} กลับหน้าแรก</button></div>
          <div class="eyebrow">EXPLORE YOUR NEXT SIGN</div><h1>${esc(S.chapterName)}</h1><p class="muted">เลือกคำที่อยากฝึก เริ่มจากคำง่าย ๆ ที่ใช้ได้ทุกวัน</p>
          <div class="grid word-grid" id="wGrid" aria-live="polite">${loading()}</div>
        </div></div>`;
      try {
        const words = await api('/api/words/' + encodeURIComponent(S.chapter));
        if (id !== viewId) return;
        $('#wGrid').innerHTML = words.length ? words.map(w => `<button class="card" data-word="${esc(w.id)}" data-name="${esc(w.label)}" ${w.has_video ? '' : 'disabled'}><span class="symbol">${icon('hand')}</span><strong>${esc(w.label)}</strong><small>${w.has_video ? 'ดูตัวอย่างและฝึกทำตาม' : 'ยังไม่มีวิดีโอ'}</small><span class="card-link">${w.has_video ? 'เริ่มฝึก' : 'ยังไม่พร้อมฝึก'} ${icon('arrow')}</span></button>`).join('') : '<p class="notice">ยังไม่มีคำศัพท์ในหมวดนี้</p>';
      } catch { if (id === viewId) $('#wGrid').innerHTML = loadError('words'); }
    } catch { if (id === viewId) $('#lessonArea').innerHTML = loadError('words'); }
  },

  hand() {
    app.innerHTML = `<section class="page">${steps(1)}${breadcrumb()}<div class="eyebrow">GET READY TO LEARN</div>
      <h1>เตรียมพร้อมก่อนฝึก “${esc(S.wordName)}”</h1><p class="muted">เปิดกล้องและชูมือให้ระบบตรวจจับ ก่อนเริ่มทำท่าตามผู้สอน</p>
      <div class="two wide"><div class="panel"><div class="panel-title"><h2>ตรวจสอบกล้อง</h2><span id="camStatus" class="status" role="status">กำลังเชื่อมต่อ</span></div>${stage()}</div>
        <div class="panel"><h2>ตรวจสอบมือที่ใช้</h2><p class="muted">หน้านี้ตรวจสอบได้ทั้งมือซ้ายและมือขวาในทุกบทเรียน ชูมือข้างใดข้างหนึ่งหรือทั้งสองข้างเพื่อทดสอบกล้อง ส่วนหน้าฝึกจะตรวจมือที่ใช้ตามท่าต้นแบบของคำนี้</p>
          <div id="det" class="detected" aria-live="polite">ชูมือขึ้นหน้ากล้อง</div>
          <div class="row"><button class="pri" id="ok" data-go="practice" disabled>พร้อมแล้ว เริ่มฝึก ${icon('arrow')}</button><button class="sec" data-go="words">เลือกคำอื่น</button></div>
          <div class="tip">${icon('tip')} จัดแสงให้เพียงพอ และให้กล้องมองเห็นมือได้ชัดเจน</div>
        </div></div></section>`;
    openCam(message => {
      $('#det').innerHTML = message.hands.length ? message.hands.map(h => `<span class="chip">${h.label === 'Right' ? 'มือขวา' : 'มือซ้าย'} (${Math.round(h.score*100)}%)</span>`).join('') : '<span class="warn">ยังไม่พบมือ ชูมือขึ้นหน้ากล้อง</span>';
      $('#ok').disabled = !message.hands.length;
    }); // Camera check uses the server's default of both hands, without a lesson filter.
  },

  practice(id) {
    teacherReady = false;
    app.innerHTML = `<section class="page">${steps(2)}${breadcrumb()}<div class="eyebrow">YOUR PRACTICE SPACE</div>
      <h1>ลองทำท่า “${esc(S.wordName)}”</h1><p class="muted">ดูตัวอย่างให้คุ้นเคย แล้วกดเริ่มบันทึกเมื่อคุณพร้อม</p>${lessonHandsNotice()}
      <div class="two"><div class="panel"><div class="panel-title"><h2>ตัวอย่างผู้สอน</h2><span class="muted small">${esc(S.wordName)}</span></div>
          <div class="stage"><video id="tv" class="${S.mirrorTeacher ? 'mir' : ''}" controls loop muted autoplay playsinline></video></div>
          <label class="opt"><input type="checkbox" id="mir" ${S.mirrorTeacher ? 'checked' : ''}> กลับด้านวิดีโอ (เหมือนกระจก)</label><p id="videoErr" class="message" role="status">กำลังโหลดวิดีโอ…</p>
        </div><div class="panel"><div class="panel-title"><h2>พื้นที่ฝึกของคุณ</h2><span id="camStatus" class="status" role="status">กำลังเชื่อมต่อ</span></div>${stage()}
          <div class="row"><button class="rec" id="start" disabled>${icon('record')} เริ่มบันทึก</button><button class="pri" id="stop" disabled>${icon('stop')} หยุดและประเมิน</button></div>
          <p id="msg" class="message" role="status">รอวิดีโอและระบบตรวจจับมือพร้อมก่อนเริ่มบันทึก</p>
        </div></div><div class="tip">${icon('tip')} ให้มืออยู่ในกรอบตลอดการฝึก แล้วกดหยุดเมื่อทำท่าครบ</div></section>`;
    const teacher = $('#tv');
    $('#mir').onchange = event => { S.mirrorTeacher = event.target.checked; teacher.classList.toggle('mir', S.mirrorTeacher); };
    teacher.oncanplay = () => { if (id !== viewId) return; teacherReady = true; $('#videoErr').textContent = ''; syncPracticeButtons(); };
    teacher.onerror = () => {
      if (id !== viewId) return;
      teacherReady = false;
      if (recording) cam?.send({type:'stop'});
      recording = false;
      $('#rec').hidden = true;
      $('#videoErr').innerHTML = '<span class="warn">โหลดวิดีโอไม่ได้ กรุณาลองใหม่หรือเลือกคำอื่น</span> <button class="sec" data-go="practice">ลองใหม่</button>';
      syncPracticeButtons();
    };
    teacher.src = `/api/video/${encodeURIComponent(S.chapter)}/${encodeURIComponent(S.word)}`;
    $('#start').onclick = () => {
      if (!cam?.ready || !teacherReady || !cam.send({type:'start'})) return;
      recording = true;
      delete $('#msg').dataset.keep;
      $('#rec').hidden = false;
      $('#msg').textContent = 'กำลังบันทึก…';
      syncPracticeButtons();
    };
    $('#stop').onclick = () => {
      if (!recording || !cam?.send({type:'evaluate',chapter:S.chapter,word:S.word,threshold:THRESHOLD})) return;
      recording = false;
      evaluating = true;
      $('#rec').hidden = true;
      $('#msg').textContent = 'กำลังประเมินผล…';
      syncPracticeButtons();
    };
    openCam(message => {
      if (evaluating) return;
      if (recording && message.recording) $('#msg').textContent = `กำลังบันทึก ${message.frames} เฟรม · ${message.hands.length ? 'พบมือ' : 'ไม่พบมือ กรุณาขยับมือเข้าในกรอบ'}`;
      else if (!recording && !$('#msg').dataset.keep) $('#msg').textContent = teacherReady ? 'พร้อมแล้ว กดเริ่มบันทึกเมื่อคุณพร้อม' : 'กำลังรอวิดีโอผู้สอน';
    }, message => {
      if (message.type === 'result') go('result', message);
      else if (message.type === 'error') {
        recording = false;
        evaluating = false;
        $('#msg').textContent = `${message.message} — กดเริ่มบันทึกแล้วทำท่าอีกครั้ง`;
        $('#msg').dataset.keep = 'true';
        $('#rec').hidden = true;
        syncPracticeButtons();
      }
    }, sessionConfig());
  },

  result(id, result) {
    const names = ['ข้อมือ','นิ้วโป้ง','นิ้วชี้','นิ้วกลาง','นิ้วนาง','นิ้วก้อย'];
    const finger = joint => joint === 0 ? 0 : Math.floor((joint-1)/4)+1;
    const summary = {};
    const frames = result.error_frames.map(frame => {
      const by = {};
      frame.errors.forEach(error => { const key = finger(error.joint_id); by[key] ||= {max:0}; by[key].max = Math.max(by[key].max,error.distance); });
      Object.keys(by).forEach(key => { summary[key] = (summary[key] || 0) + 1; });
      return {frame,by,worst:Math.max(0,...Object.values(by).map(value => value.max))};
    });
    const top = Object.entries(summary).sort((a,b) => b[1]-a[1]).slice(0,3);
    const passed = result.passed === true;
    const score = Number.isFinite(result.display_score) ? Math.max(0,Math.min(100,result.display_score)) : 0;
    const card = ({frame,by}, i) => `<article class="panel error-card"><h3>ท่าที่ควรปรับ #${i+1}</h3><small>ตรงกับท่าผู้สอน #${esc(frame.template_kf_id)}</small>
      <div class="err"><img src="${/^data:image\/(jpeg|png);base64,/.test(frame.image) ? esc(frame.image) : ''}" alt="ภาพการฝึกของคุณในท่าที่ควรปรับ ${i+1}" loading="lazy">
        <div><p>สิ่งที่ควรปรับ:</p><ul>${(frame.hints && frame.hints.length ? frame.hints.map(h => `<li><b>${esc((h.hand ? h.hand + ' ' : '') + h.finger)}</b> ${esc(h.text)}</li>`).join('') : '<li>ลองดูท่าผู้สอนอีกครั้ง แล้วเทียบรูปมือของคุณ</li>')}</ul>
          <details><summary>รายละเอียดสำหรับผู้พัฒนา</summary><ul>${frame.errors.map(error => `<li><b>[${esc(error.side)}]</b> ${esc(error.joint_name)} — ${esc(error.distance)}</li>`).join('')}</ul></details>
        </div></div></article>`;
    const chips = top.length ? `<p>จุดที่ควรฝึกเพิ่ม:</p>${top.map(([key]) => `<span class="chip bad">${names[key]}</span>`).join('')}` : '';
    const resultPanel = passed
      ? `<div class="panel result-summary"><div class="score-ring" style="--score:${score}%" aria-label="คะแนน ${Math.round(score)} เปอร์เซ็นต์"><span><strong class="score">${Math.round(score)}%</strong><small>คะแนน</small></span></div>
          <div class="result-copy"><h2>${frames.length ? 'ผ่านแล้ว! ปรับอีกนิดจะยิ่งดี' : 'ทำได้ดีมาก!'}</h2>${chips}</div></div>`
      : `<div class="panel"><span class="status error">ไม่ผ่าน</span><h2 style="margin-top:12px">ลองทำท่าอีกครั้ง</h2><p class="muted">ดูวิดีโอผู้สอนอีกรอบ แล้วฝึกใหม่ได้เลย</p>${chips}</div>`;
    app.innerHTML = `<section class="page">${steps(3)}${breadcrumb()}<div class="eyebrow">EVERY PRACTICE IS PROGRESS</div>
      <h1>ผลการฝึกของคุณ</h1><p class="muted">คำว่า “${esc(S.wordName)}” · เรียนรู้จากแต่ละครั้ง แล้วค่อย ๆ พัฒนา</p>
      ${resultPanel}
      ${frames.slice(0,2).map(card).join('')}
      <div class="row"><button class="pri" data-go="practice">${icon('repeat')} ฝึกคำนี้อีกครั้ง</button><button class="sec" data-go="words">เลือกคำอื่น ${icon('arrow')}</button></div></section>`;
  }
};

// These delegated events cover both the static header and dynamic screens.
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button || button.disabled) return;
  if (button.dataset.go) go(button.dataset.go);
  else if (button.dataset.chapter) {
    S.chapter = button.dataset.chapter;
    S.chapterName = button.dataset.name;
    S.word = null;
    S.wordName = '';
    go('words');
  } else if (button.dataset.word) {
    S.word = button.dataset.word;
    S.wordName = button.dataset.name;
    go('hand');
  }
});
window.addEventListener('pagehide', () => cam?.stop());
document.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); });
go('home');
