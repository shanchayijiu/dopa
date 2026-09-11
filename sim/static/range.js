"use strict";

const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d");
const lockHint = document.getElementById("lockhint");
const el = (id) => document.getElementById(id);

const PALETTE = ["#ffd60a", "#ff5a3c", "#3cb4ff", "#78ff78"];

let cfg = { width: 320, height: 320, center: [160, 160], sens: 1.0, mode: "bounce", count: 1 };
let targets = [];
let overlay = null;
let dpr = window.devicePixelRatio || 1;

let ws = null;
let locked = false;
let lastClient = null;
let frames = 0;
let fps = 0;
let lastFpsT = performance.now();
let clicks = 0;
let hits = 0;

const ballImg = new Image();
ballImg.src = "/static/assets/ball.png?v=4";
const frisbeeImg = new Image();
frisbeeImg.src = "/static/assets/frisbee.svg?v=4";

function resize() {
  dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(window.innerWidth * dpr);
  canvas.height = Math.floor(window.innerHeight * dpr);
  canvas.style.width = window.innerWidth + "px";
  canvas.style.height = window.innerHeight + "px";
  el("dpr").textContent = dpr.toFixed(2);
  el("vp").textContent = window.innerWidth + "x" + window.innerHeight;
}

function layout() {
  const cssW = cfg.width / dpr;
  const cssH = cfg.height / dpr;
  const left = (window.innerWidth - cssW) / 2;
  const top = (window.innerHeight - cssH) / 2;
  return { left, top, cssW, cssH, scale: 1 / dpr };
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => {
    el("status").textContent = "已连接";
    send({
      type: "hello",
      dpr,
      innerW: window.innerWidth,
      innerH: window.innerHeight,
      screenX: window.screenX,
      screenY: window.screenY,
      t: performance.now(),
    });
  };
  ws.onclose = () => {
    el("status").textContent = "已断开，重连中...";
    setTimeout(connect, 1000);
  };
  ws.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    if (msg.type === "config") {
      cfg = Object.assign(cfg, msg.config);
      el("count").value = cfg.count;
      el("countv").textContent = cfg.count;
      document.querySelectorAll(".mode").forEach((b) => {
        b.classList.toggle("active", b.dataset.mode === cfg.mode);
      });
    } else if (msg.type === "frame") {
      targets = msg.targets || [];
    } else if (msg.type === "overlay") {
      overlay = msg.data;
    } else if (msg.type === "hit") {
      clicks += 1;
      if (msg.hit) hits += 1;
      el("clicks").textContent = clicks;
      el("hits").textContent = hits;
    }
  };
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

function drawSprite(img, x, y, w, h, color) {
  ctx.save();
  ctx.translate(x, y);
  if (img.complete && img.naturalWidth > 0) {
    ctx.drawImage(img, -w / 2, -h / 2, w, h);
  } else {
    ctx.beginPath();
    ctx.arc(0, 0, Math.min(w, h) / 2, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  }
  ctx.restore();
}

function draw() {
  const { left, top, cssW, cssH } = layout();

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#0b0e13";
  ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);

  ctx.fillStyle = "#121826";
  ctx.fillRect(left, top, cssW, cssH);
  ctx.strokeStyle = "#33435c";
  ctx.lineWidth = 2;
  ctx.strokeRect(left, top, cssW, cssH);

  ctx.save();
  ctx.beginPath();
  ctx.rect(left, top, cssW, cssH);
  ctx.clip();
  const s = 1 / dpr;
  for (const t of targets) {
    if (t.alive === false) continue;
    const cx = left + t.x * s;
    const cy = top + t.y * s;
    const w = t.w * s;
    const h = t.h * s;
    const color = PALETTE[t.color % PALETTE.length] || "#ffd60a";
    const img = t.sprite === "frisbee" ? frisbeeImg : ballImg;
    drawSprite(img, cx, cy, w, h, color);
  }

  if (overlay && Array.isArray(overlay.boxes)) {
    const inW = overlay.input_w || cfg.width;
    const k = (cfg.width / inW) * s;
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = "#00e0a0";
    for (const b of overlay.boxes) {
      if (!b || b.length < 4) continue;
      const cx = left + b[0] * k;
      const cy = top + b[1] * k;
      ctx.strokeRect(cx - (b[2] * k) / 2, cy - (b[3] * k) / 2, b[2] * k, b[3] * k);
    }
    if (overlay.predict) {
      ctx.strokeStyle = "#ff4d6d";
      ctx.beginPath();
      ctx.arc(left + overlay.predict[0] * k, top + overlay.predict[1] * k, 6, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  const crossX = left + cssW / 2;
  const crossY = top + cssH / 2;
  ctx.strokeStyle = "#ff2d2d";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(crossX - 9, crossY);
  ctx.lineTo(crossX - 3, crossY);
  ctx.moveTo(crossX + 3, crossY);
  ctx.lineTo(crossX + 9, crossY);
  ctx.moveTo(crossX, crossY - 9);
  ctx.lineTo(crossX, crossY - 3);
  ctx.moveTo(crossX, crossY + 3);
  ctx.lineTo(crossX, crossY + 9);
  ctx.stroke();
  ctx.restore();
}

function loop() {
  draw();
  frames += 1;
  const now = performance.now();
  if (now - lastFpsT >= 500) {
    fps = Math.round((frames * 1000) / (now - lastFpsT));
    frames = 0;
    lastFpsT = now;
    el("fps").textContent = fps;
    el("n").textContent = targets.filter((t) => t.alive !== false).length;
  }
  requestAnimationFrame(loop);
}

function readOverlayPoint(e) {
  return { dx: e.movementX || 0, dy: e.movementY || 0 };
}

function onMouseMove(e) {
  let dx = 0;
  let dy = 0;
  if (locked) {
    dx = (e.movementX || 0) * dpr;
    dy = (e.movementY || 0) * dpr;
  } else if (lastClient) {
    dx = (e.clientX - lastClient.x) * dpr;
    dy = (e.clientY - lastClient.y) * dpr;
  }
  lastClient = { x: e.clientX, y: e.clientY };
  if (dx !== 0 || dy !== 0) {
    send({ type: "mouse_delta", dx, dy });
  }
}

function onMouseDown(e) {
  send({ type: "click", x: e.clientX, y: e.clientY, button: e.button, t: performance.now() });
}

function requestLock() {
  lockHint.classList.add("hidden");
  if (canvas.requestPointerLock) {
    try {
      canvas.requestPointerLock();
    } catch (err) {}
  }
}

function setupInput() {
  lockHint.addEventListener("click", requestLock);
  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mousedown", (e) => {
    if (!lockHint.classList.contains("hidden")) {
      requestLock();
      return;
    }
    onMouseDown(e);
  });
  document.addEventListener("pointerlockchange", () => {
    locked = document.pointerLockElement === canvas;
    if (!locked) lockHint.classList.remove("hidden");
  });
  window.addEventListener("keydown", (e) => {
    if (e.key === "f" || e.key === "F") {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen();
    }
  });
  window.addEventListener("resize", resize);
}

function setupPanel() {
  document.querySelectorAll(".mode").forEach((b) => {
    b.addEventListener("click", () => send({ type: "control", mode: b.dataset.mode }));
  });
  el("count").addEventListener("input", (e) => {
    el("countv").textContent = e.target.value;
    send({ type: "control", count: Number(e.target.value) });
  });
  const speed = el("speed");
  speed.addEventListener("input", (e) => {
    const v = Number(e.target.value);
    el("speedv").textContent = v;
    send({ type: "control", min_speed: v * 0.6, max_speed: v });
  });
  const sens = el("sens");
  sens.addEventListener("input", (e) => {
    el("sensv").textContent = Number(e.target.value).toFixed(1);
    send({ type: "control", sens: Number(e.target.value) });
  });
}

resize();
setupInput();
setupPanel();
connect();
requestAnimationFrame(loop);
