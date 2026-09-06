/* =========================================================================
   To-Do Rewards — логика мини-приложения
   ========================================================================= */
'use strict';

const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

const state = {
  user: null,
  tasks: [],
  achievements: [],
  shop: [],
  filter: 'active',
  tab: 'today',
  draft: { emoji: '📌', priority: 1, when: 'none', repeat: 'none' },
};

const EMOJIS = ['📌','🛒','📞','💼','🏋️','📚','🧹','💳','🎁','🏥','💻','✉️','🍳','🚗','🐶','🌱','🎨','🎯','☕','🔥'];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* ----------------------------------------------------------- Telegram */

function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
  if (tg.setHeaderColor) { try { tg.setHeaderColor('#12081f'); } catch (e) {} }
  if (tg.enableClosingConfirmation) { try { tg.enableClosingConfirmation(); } catch (e) {} }
}

function haptic(type = 'light') {
  if (!tg || !tg.HapticFeedback) return;
  try {
    if (type === 'success' || type === 'error' || type === 'warning') {
      tg.HapticFeedback.notificationOccurred(type);
    } else {
      tg.HapticFeedback.impactOccurred(type);
    }
  } catch (e) { /* не критично */ }
}

/* ---------------------------------------------------------------- API */

async function api(path, options = {}) {
  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    { 'X-Telegram-Init-Data': (tg && tg.initData) || '' },
    options.headers || {}
  );
  const res = await fetch('/api' + path, Object.assign({}, options, { headers }));
  if (!res.ok) {
    let message = 'Что-то пошло не так 😔';
    try { const body = await res.json(); message = body.detail || message; } catch (e) {}
    throw new Error(message);
  }
  return res.json();
}

/* ------------------------------------------------------------ утилиты */

function tzOffset() { return state.user ? state.user.tz_offset : 3; }

function localDate(ts) {
  return new Date((ts + tzOffset() * 3600) * 1000);
}

function nowTs() { return Math.floor(Date.now() / 1000); }

function dayKey(ts) {
  const d = localDate(ts);
  return d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0') + '-' + String(d.getUTCDate()).padStart(2, '0');
}

function fmtWhen(ts) {
  if (!ts) return '';
  const d = localDate(ts);
  const time = String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0');
  const today = dayKey(nowTs());
  const key = dayKey(ts);
  const tomorrow = dayKey(nowTs() + 86400);
  const yesterday = dayKey(nowTs() - 86400);
  if (key === today) return 'сегодня ' + time;
  if (key === tomorrow) return 'завтра ' + time;
  if (key === yesterday) return 'вчера ' + time;
  return String(d.getUTCDate()).padStart(2, '0') + '.' + String(d.getUTCMonth() + 1).padStart(2, '0') + ' ' + time;
}

function escapeHtml(text) {
  return String(text || '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

const REPEAT_LABEL = { daily: '🔁 каждый день', weekly: '🔁 раз в неделю', weekdays: '💼 по будням' };

/* ------------------------------------------------------------- тосты */

function toast(message, ms = 2600) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = message;
  $('#toasts').appendChild(el);
  setTimeout(() => {
    el.classList.add('out');
    setTimeout(() => el.remove(), 400);
  }, ms);
}

function floater(text, x, y, color) {
  const el = document.createElement('div');
  el.className = 'floater';
  el.textContent = text;
  el.style.left = x + 'px';
  el.style.top = y + 'px';
  el.style.color = color || '#fff';
  $('#floaters').appendChild(el);
  setTimeout(() => el.remove(), 1400);
}

/* ---------------------------------------------------------- конфетти */

const confetti = (() => {
  const canvas = $('#confetti');
  const ctx = canvas.getContext('2d');
  let particles = [];
  let raf = null;

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
    canvas.style.width = window.innerWidth + 'px';
    canvas.style.height = window.innerHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resize);
  resize();

  const palette = ['#f472b6', '#facc15', '#34d399', '#38bdf8', '#a78bfa', '#fb7185', '#fde68a'];

  function burst(x, y, count = 46, power = 1) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = (2 + Math.random() * 7) * power;
      particles.push({
        x, y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 3 * power,
        size: 4 + Math.random() * 6,
        rot: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.4,
        color: palette[(Math.random() * palette.length) | 0],
        life: 1,
        shape: Math.random() > 0.4 ? 'rect' : 'circle',
      });
    }
    if (!raf) raf = requestAnimationFrame(tick);
  }

  function rain(count = 90) {
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * window.innerWidth,
        y: -20 - Math.random() * 200,
        vx: (Math.random() - 0.5) * 2,
        vy: 2 + Math.random() * 4,
        size: 5 + Math.random() * 7,
        rot: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.3,
        color: palette[(Math.random() * palette.length) | 0],
        life: 1,
        shape: Math.random() > 0.4 ? 'rect' : 'circle',
      });
    }
    if (!raf) raf = requestAnimationFrame(tick);
  }

  function tick() {
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    particles = particles.filter((p) => p.life > 0 && p.y < window.innerHeight + 60);
    particles.forEach((p) => {
      p.vy += 0.16;
      p.vx *= 0.995;
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.vr;
      p.life -= 0.006;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.globalAlpha = Math.max(0, Math.min(1, p.life));
      ctx.fillStyle = p.color;
      if (p.shape === 'rect') {
        ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      } else {
        ctx.beginPath();
        ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    });
    if (particles.length) {
      raf = requestAnimationFrame(tick);
    } else {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      raf = null;
    }
  }

  return { burst, rain };
})();

/* ------------------------------------------------------------ рендер */

function applyState(payload) {
  state.user = payload.user;
  state.tasks = payload.tasks;
  state.achievements = payload.achievements;
  state.shop = payload.shop;
  render();
}

function render() {
  renderHero();
  renderToday();
  renderAll();
  renderAchievements();
  renderShop();
  document.documentElement.dataset.theme = state.user.theme || 'aurora';
}

function renderHero() {
  const user = state.user;
  const level = user.level;

  $('#greeting').textContent = 'Привет, ' + (user.name ? user.name.split(' ')[0] : 'друг') + '! 👋';
  $('#levelTitle').textContent = level.title;
  $('#levelEmoji').textContent = level.emoji;
  $('#levelNum').textContent = 'ур. ' + level.level;
  $('#xpText').textContent = level.xp + ' / ' + level.xp_next_level + ' XP  ·  ещё ' + level.xp_to_next + ' до ур. ' + (level.level + 1);

  const circumference = 2 * Math.PI * 38;
  $('#ringFg').style.strokeDashoffset = String(circumference * (1 - level.progress));
  $('#xpFill').style.width = (level.progress * 100).toFixed(1) + '%';

  bumpStat('#statCoins', user.coins, 'монет');
  bumpStat('#statStreak', user.streak, user.streak === 1 ? 'день' : 'дней');
  bumpStat('#statDone', user.total_done, 'сделано');
}

function bumpStat(selector, value, label) {
  const el = $(selector);
  const bold = el.querySelector('b');
  const prev = Number(bold.textContent);
  bold.textContent = value;
  el.querySelector('i').textContent = label;
  if (prev !== value && !Number.isNaN(prev)) {
    el.classList.add('bump');
    setTimeout(() => el.classList.remove('bump'), 380);
  }
}

function todayTasks() {
  const today = dayKey(nowTs());
  return state.tasks.filter((t) => {
    if (t.done) {
      return t.done_at && dayKey(t.done_at) === today;
    }
    const when = t.remind_at || t.due_at;
    return !when || dayKey(when) <= today;
  });
}

function renderToday() {
  const tasks = todayTasks();
  const done = tasks.filter((t) => t.done).length;
  const percent = tasks.length ? Math.round((done / tasks.length) * 100) : 0;

  $('#dayPercent').textContent = percent + '%';
  $('#dayFill').style.width = percent + '%';
  $('#dayHint').textContent =
    tasks.length === 0 ? 'Задач на сегодня нет — добавь первую ✨'
    : percent === 100 ? 'Идеальный день! Все задачи закрыты 🎉'
    : percent >= 50 ? 'Больше половины позади, дожимай! 🔥'
    : 'Сделано ' + done + ' из ' + tasks.length + ' — вперёд 💪';

  const sorted = tasks.slice().sort(sortTasks);
  renderList($('#listToday'), sorted, {
    emoji: '🌤',
    title: 'На сегодня пусто',
    text: 'Нажми «+», чтобы добавить задачу',
  });
}

function renderAll() {
  let tasks = state.tasks.slice();
  if (state.filter === 'active') tasks = tasks.filter((t) => !t.done);
  else if (state.filter === 'done') tasks = tasks.filter((t) => t.done);
  else if (state.filter === 'high') tasks = tasks.filter((t) => t.priority === 2 && !t.done);

  renderList($('#listAll'), tasks.sort(sortTasks), {
    emoji: '🗂',
    title: 'Здесь пока пусто',
    text: 'Задачи появятся, как только ты их добавишь',
  });
}

function sortTasks(a, b) {
  if (a.done !== b.done) return a.done - b.done;
  const aw = a.remind_at || a.due_at || 9e9;
  const bw = b.remind_at || b.due_at || 9e9;
  if (aw !== bw) return aw - bw;
  return b.priority - a.priority;
}

function renderList(container, tasks, empty) {
  if (!tasks.length) {
    container.innerHTML =
      '<div class="empty"><span class="empty-emoji">' + empty.emoji + '</span>' +
      '<div class="empty-title">' + empty.title + '</div><div>' + empty.text + '</div></div>';
    return;
  }

  container.innerHTML = tasks.map((task, index) => {
    const when = task.remind_at || task.due_at;
    let whenClass = 'meta';
    if (when && !task.done) {
      if (when < nowTs()) whenClass = 'meta late';
      else if (when - nowTs() < 3 * 3600) whenClass = 'meta soon';
    }
    const chips = [];
    if (when) chips.push('<span class="' + whenClass + '">⏰ ' + fmtWhen(when) + '</span>');
    if (task.repeat && task.repeat !== 'none') chips.push('<span class="meta">' + REPEAT_LABEL[task.repeat] + '</span>');
    if (task.note) chips.push('<span class="meta">📝 ' + escapeHtml(task.note.slice(0, 24)) + '</span>');

    return '' +
      '<article class="task' + (task.done ? ' done' : '') + '" data-id="' + task.id + '" data-p="' + task.priority + '" style="animation-delay:' + Math.min(index * 45, 400) + 'ms">' +
        '<button class="check' + (task.done ? ' on' : '') + '" data-action="toggle">' + (task.done ? '✓' : '') + '</button>' +
        '<div class="task-body">' +
          '<div class="task-title"><span class="task-emoji">' + (task.emoji || '📌') + '</span>' + escapeHtml(task.title) + '</div>' +
          (chips.length ? '<div class="task-meta">' + chips.join('') + '</div>' : '') +
        '</div>' +
        '<button class="task-del" data-action="delete">🗑</button>' +
      '</article>';
  }).join('');
}

function renderAchievements() {
  const unlocked = state.achievements.filter((a) => a.unlocked).length;
  $('#achCount').textContent = unlocked + ' из ' + state.achievements.length;
  $('#achGrid').innerHTML = state.achievements.map((a, index) => '' +
    '<div class="ach ' + (a.unlocked ? 'unlocked' : 'locked') + '" style="animation-delay:' + Math.min(index * 40, 400) + 'ms">' +
      '<span class="ach-emoji">' + (a.unlocked ? a.emoji : '🔒') + '</span>' +
      '<div class="ach-title">' + escapeHtml(a.title) + '</div>' +
      '<div class="ach-desc">' + escapeHtml(a.desc) + '</div>' +
      '<div class="ach-coins">' + (a.unlocked ? 'получено +' + a.coins + ' 🪙' : 'награда ' + a.coins + ' 🪙') + '</div>' +
    '</div>').join('');
}

function renderShop() {
  $('#balance').innerHTML = '🪙 <b>' + state.user.coins + '</b> монет';

  const draw = (items) => items.map((item, index) => {
    const owned = item.owned;
    const active = item.active;
    const affordable = state.user.coins >= item.price;
    let label = item.price + ' 🪙';
    let cls = 'buy-btn';
    if (item.type === 'theme') {
      if (active) { label = '✔️ Активна'; cls += ' owned'; }
      else if (owned) { label = 'Включить'; }
      else if (!affordable) { cls += ' poor'; }
    } else if (!affordable) {
      cls += ' poor';
    }
    return '' +
      '<div class="shop-item' + (active ? ' active-theme' : '') + '" style="animation-delay:' + Math.min(index * 45, 350) + 'ms">' +
        '<span class="shop-emoji">' + item.emoji + '</span>' +
        '<div class="shop-body">' +
          '<div class="shop-title">' + escapeHtml(item.title) + '</div>' +
          '<div class="shop-desc">' + escapeHtml(item.desc) + '</div>' +
        '</div>' +
        '<button class="' + cls + '" data-buy="' + item.code + '">' + label + '</button>' +
      '</div>';
  }).join('');

  $('#shopThemes').innerHTML = draw(state.shop.filter((i) => i.type === 'theme'));
  $('#shopRewards').innerHTML = draw(state.shop.filter((i) => i.type === 'reward'));
}

/* --------------------------------------------------------- действия */

async function toggleTask(id, checkEl) {
  const task = state.tasks.find((t) => t.id === id);
  if (!task) return;
  const makeDone = !task.done;

  const card = checkEl.closest('.task');
  if (makeDone) {
    haptic('success');
    checkEl.classList.add('on');
    checkEl.textContent = '✓';
    card.classList.add('completing');
    const rect = checkEl.getBoundingClientRect();
    confetti.burst(rect.left + rect.width / 2, rect.top + rect.height / 2, 42, 1);
  } else {
    haptic('light');
  }

  try {
    const data = await api('/tasks/' + id, {
      method: 'PATCH',
      body: JSON.stringify({ done: makeDone }),
    });
    const reward = data.reward;
    applyState(data.state);

    if (reward && makeDone) {
      const rect = card ? card.getBoundingClientRect() : { left: window.innerWidth / 2, top: 200, width: 0 };
      floater('+' + reward.xp + ' XP', rect.left + (rect.width || 0) / 2, rect.top, '#a5f3fc');
      setTimeout(() => floater('+' + reward.coins + ' 🪙', rect.left + (rect.width || 0) / 2 + 40, rect.top + 10, '#fde68a'), 160);

      let text = '🎉 <b>+' + reward.xp + ' XP</b> и <b>+' + reward.coins + ' 🪙</b>';
      if (reward.bonuses && reward.bonuses.length) text += '<br><span style="opacity:.75">' + reward.bonuses.join(' · ') + '</span>';
      toast(text);

      if (reward.streak_grew && reward.streak > 1) {
        setTimeout(() => toast('🔥 Серия <b>' + reward.streak + '</b> дней подряд!'), 500);
      }
      (reward.achievements || []).forEach((ach, i) => {
        setTimeout(() => {
          toast('🏅 <b>' + ach.title + '</b> ' + ach.emoji + '<br><span style="opacity:.75">' + ach.desc + ' · +' + ach.coins + ' 🪙</span>', 3400);
          confetti.rain(40);
          haptic('success');
        }, 900 + i * 900);
      });
      if (reward.level_up) setTimeout(() => showLevelUp(), 700);
      if (reward.next_task) setTimeout(() => toast('🔁 Повтор задачи запланирован'), 400);
    }
  } catch (err) {
    haptic('error');
    toast('😔 ' + err.message);
    render();
  }
}

async function deleteTask(id, cardEl) {
  haptic('medium');
  cardEl.classList.add('removing');
  try {
    const data = await api('/tasks/' + id, { method: 'DELETE' });
    setTimeout(() => applyState(data.state), 260);
    toast('🗑 Задача удалена');
  } catch (err) {
    cardEl.classList.remove('removing');
    toast('😔 ' + err.message);
  }
}

function showLevelUp() {
  const level = state.user.level;
  $('#luLevel').textContent = level.level;
  $('#luSub').textContent = level.emoji + ' ' + level.title;
  $('#luEmoji').textContent = '🎉';
  $('#levelup').classList.add('show');
  confetti.rain(120);
  haptic('success');
  setTimeout(() => confetti.burst(window.innerWidth / 2, window.innerHeight / 2, 60, 1.3), 300);
}

async function buyItem(code, button) {
  haptic('medium');
  button.disabled = true;
  try {
    const data = await api('/shop/buy', { method: 'POST', body: JSON.stringify({ code }) });
    applyState(data.state);
    const item = data.result.item;
    if (data.result.applied) {
      toast('🎨 Тема «' + item.title.replace(/^Тема «|»$/g, '') + '» включена!');
    } else {
      toast('🛍 <b>' + item.title + '</b> ' + item.emoji + '<br><span style="opacity:.75">Наслаждайся — ты заслужил!</span>');
      const rect = button.getBoundingClientRect();
      confetti.burst(rect.left + rect.width / 2, rect.top, 36, 0.9);
    }
    haptic('success');
    (data.result.achievements || []).forEach((ach, i) => {
      setTimeout(() => toast('🏅 <b>' + ach.title + '</b> ' + ach.emoji), 800 + i * 800);
    });
  } catch (err) {
    haptic('error');
    toast('😔 ' + err.message);
  } finally {
    button.disabled = false;
  }
}

/* -------------------------------------------------- лист новой задачи */

function computeWhen() {
  const when = state.draft.when;
  const now = new Date();
  const offsetMs = tzOffset() * 3600 * 1000;

  const localNow = new Date(now.getTime() + offsetMs);
  const atLocal = (dayShift, hours, minutes) => {
    const d = new Date(localNow.getTime());
    d.setUTCDate(d.getUTCDate() + dayShift);
    d.setUTCHours(hours, minutes, 0, 0);
    return Math.floor((d.getTime() - offsetMs) / 1000);
  };

  if (when === 'none') return null;
  if (when === '1h') return Math.floor(now.getTime() / 1000) + 3600;
  if (when === 'today18') {
    let ts = atLocal(0, 18, 0);
    if (ts <= Math.floor(now.getTime() / 1000)) ts = atLocal(1, 18, 0);
    return ts;
  }
  if (when === 'tomorrow9') return atLocal(1, 9, 0);
  if (when === 'custom') {
    const value = $('#customWhen').value;
    if (!value) return null;
    const [datePart, timePart] = value.split('T');
    const [y, m, d] = datePart.split('-').map(Number);
    const [hh, mm] = timePart.split(':').map(Number);
    return Math.floor(Date.UTC(y, m - 1, d, hh, mm) / 1000) - tzOffset() * 3600;
  }
  return null;
}

function openSheet() {
  haptic('light');
  $('#backdrop').classList.add('show');
  $('#sheet').classList.add('show');
  $('#fab').classList.add('open');
  setTimeout(() => $('#taskTitle').focus(), 320);
}

function closeSheet() {
  $('#backdrop').classList.remove('show');
  $('#sheet').classList.remove('show');
  $('#fab').classList.remove('open');
  $('#taskTitle').blur();
}

function resetDraft() {
  state.draft = { emoji: '📌', priority: 1, when: 'none', repeat: 'none' };
  $('#taskTitle').value = '';
  $('#customWhen').value = '';
  $('#customWhen').classList.add('hidden');
  $('#parseHint').textContent = '💡 Можно писать «завтра в 18:00 позвонить маме»';
  $('#parseHint').classList.remove('parsed');
  $$('#emojiRow .emoji-btn').forEach((b, i) => b.classList.toggle('active', i === 0));
  setPriority(1);
  $$('#whenChips .chip').forEach((c) => c.classList.toggle('active', c.dataset.when === 'none'));
  $$('#repeatChips .chip').forEach((c) => c.classList.toggle('active', c.dataset.repeat === 'none'));
  updateRewardPreview();
}

function setPriority(value) {
  state.draft.priority = value;
  $$('#prioritySeg button').forEach((b) => b.classList.toggle('active', Number(b.dataset.p) === value));
  $('#segPill').style.transform = 'translateX(calc(' + value + ' * (100% + 4px)))';
  updateRewardPreview();
}

function updateRewardPreview() {
  const base = 10 + [0, 5, 15][state.draft.priority];
  const streak = state.user ? state.user.streak : 0;
  const mult = Math.min(2, 1 + 0.1 * Math.max(0, streak - 1));
  const xp = Math.round(base * mult);
  $('#rewardPreview').textContent = 'Награда за выполнение: +' + xp + ' XP · +' + Math.max(1, Math.floor(xp / 2)) + ' 🪙' +
    (mult > 1 ? ' (серия ×' + mult.toFixed(1) + ')' : '');
}

const NL_HINT = /(завтра|послезавтра|сегодня|через\s+\d+|\b\d{1,2}[:.]\d{2}\b|\bв\s+\d{1,2}\b|пн|вт|ср|чт|пт|сб|вс)/i;

function onTitleInput() {
  const value = $('#taskTitle').value;
  const hint = $('#parseHint');
  if (NL_HINT.test(value) && state.draft.when === 'none') {
    hint.textContent = '⏰ Похоже, здесь есть время — распознаю его автоматически';
    hint.classList.add('parsed');
  } else {
    hint.textContent = '💡 Можно писать «завтра в 18:00 позвонить маме»';
    hint.classList.remove('parsed');
  }
}

async function saveTask() {
  const title = $('#taskTitle').value.trim();
  if (!title) {
    haptic('error');
    $('#taskTitle').focus();
    toast('✍️ Напиши, что нужно сделать');
    return;
  }
  const button = $('#saveTask');
  button.disabled = true;
  const remind = computeWhen();

  try {
    const data = await api('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        title,
        emoji: state.draft.emoji,
        priority: state.draft.priority,
        repeat: state.draft.repeat,
        due_at: remind,
        remind_at: remind,
        smart: remind === null,
      }),
    });
    applyState(data.state);
    haptic('success');
    closeSheet();
    resetDraft();
    const task = data.task;
    const when = task.remind_at || task.due_at;
    toast('✨ <b>' + escapeHtml(task.title) + '</b>' + (when ? '<br><span style="opacity:.75">⏰ напомню ' + fmtWhen(when) + '</span>' : ''));
    confetti.burst(window.innerWidth / 2, window.innerHeight - 120, 26, 0.8);
  } catch (err) {
    haptic('error');
    toast('😔 ' + err.message);
  } finally {
    button.disabled = false;
  }
}

/* -------------------------------------------------------- навигация */

function switchTab(name) {
  state.tab = name;
  haptic('light');
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $$('.screen').forEach((s) => s.classList.toggle('active', s.dataset.screen === name));
  const index = ['today', 'all', 'rewards', 'shop'].indexOf(name);
  $('#tabPill').style.transform = 'translateX(calc(' + index + ' * (100% + 4px)))';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ------------------------------------------------------- инициализация */

function bindEvents() {
  $('#emojiRow').innerHTML = EMOJIS.map((e, i) =>
    '<button class="emoji-btn' + (i === 0 ? ' active' : '') + '" data-emoji="' + e + '">' + e + '</button>').join('');

  $('#emojiRow').addEventListener('click', (event) => {
    const button = event.target.closest('.emoji-btn');
    if (!button) return;
    haptic('light');
    state.draft.emoji = button.dataset.emoji;
    $$('#emojiRow .emoji-btn').forEach((b) => b.classList.toggle('active', b === button));
  });

  $('#prioritySeg').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-p]');
    if (!button) return;
    haptic('light');
    setPriority(Number(button.dataset.p));
  });

  $('#whenChips').addEventListener('click', (event) => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    haptic('light');
    state.draft.when = chip.dataset.when;
    $$('#whenChips .chip').forEach((c) => c.classList.toggle('active', c === chip));
    $('#customWhen').classList.toggle('hidden', chip.dataset.when !== 'custom');
    onTitleInput();
  });

  $('#repeatChips').addEventListener('click', (event) => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    haptic('light');
    state.draft.repeat = chip.dataset.repeat;
    $$('#repeatChips .chip').forEach((c) => c.classList.toggle('active', c === chip));
  });

  $('#taskTitle').addEventListener('input', onTitleInput);
  $('#taskTitle').addEventListener('keydown', (e) => { if (e.key === 'Enter') saveTask(); });
  $('#saveTask').addEventListener('click', saveTask);
  $('#fab').addEventListener('click', () => {
    if ($('#sheet').classList.contains('show')) closeSheet(); else openSheet();
  });
  $('#backdrop').addEventListener('click', closeSheet);

  $('#tabs').addEventListener('click', (event) => {
    const tab = event.target.closest('.tab');
    if (tab) switchTab(tab.dataset.tab);
  });

  $('#filters').addEventListener('click', (event) => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    haptic('light');
    state.filter = chip.dataset.filter;
    $$('#filters .chip').forEach((c) => c.classList.toggle('active', c === chip));
    renderAll();
  });

  document.addEventListener('click', (event) => {
    const action = event.target.closest('[data-action]');
    if (action) {
      const card = action.closest('.task');
      const id = Number(card.dataset.id);
      if (action.dataset.action === 'toggle') toggleTask(id, action);
      if (action.dataset.action === 'delete') deleteTask(id, card);
      return;
    }
    const buy = event.target.closest('[data-buy]');
    if (buy) buyItem(buy.dataset.buy, buy);
  });

  $('#clearDone').addEventListener('click', async () => {
    haptic('medium');
    try {
      const data = await api('/tasks/clear-done', { method: 'POST' });
      applyState(data.state);
      toast('🧹 Убрано: <b>' + data.removed + '</b>');
    } catch (err) {
      toast('😔 ' + err.message);
    }
  });

  $('#luClose').addEventListener('click', () => {
    haptic('light');
    $('#levelup').classList.remove('show');
  });
}

async function syncTimezone() {
  if (!state.user) return;
  const offset = -Math.round(new Date().getTimezoneOffset() / 60);
  if (offset === state.user.tz_offset) return;
  try {
    const data = await api('/settings', { method: 'POST', body: JSON.stringify({ tz_offset: offset }) });
    applyState(data.state);
  } catch (e) { /* не критично */ }
}

async function boot() {
  initTelegram();
  bindEvents();
  try {
    const data = await api('/state');
    applyState(data);
    resetDraft();
    $('#splash').classList.add('gone');
    $('#app').classList.remove('hidden');
    setTimeout(() => { $('#tabPill').style.transform = 'translateX(0)'; }, 50);

    syncTimezone();  // часовой пояс устройства — чтобы напоминания приходили вовремя

    if (state.user.total_done === 0 && state.tasks.length === 0) {
      setTimeout(() => toast('👋 Добро пожаловать! Нажми «+» и добавь первую задачу'), 900);
    }
  } catch (err) {
    $('#splash').innerHTML =
      '<div class="splash-emoji">😔</div><div class="splash-text">' + escapeHtml(err.message) + '</div>';
  }
}

boot();
