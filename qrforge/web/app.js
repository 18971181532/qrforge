"use strict";

/* QRForge workbench.  All heavy lifting happens server-side through the
   local API; the browser only renders matrices on canvas. */

const $ = (id) => document.getElementById(id);
let STATE = { gen: null, heal: { rows: null, flips: [], base: null, seed: 0, cells: 24 } };

function api(path, body) {
  return fetch(path, body ? {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  } : undefined).then((r) => r.json());
}

/* ------------------------------------------------------------------ tabs */

for (const btn of document.querySelectorAll("nav button")) {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
  });
}

/* --------------------------------------------------------------- canvas */

function drawMatrix(canvas, rows, opts) {
  opts = opts || {};
  const n = rows.length;
  const cell = Math.max(6, Math.floor(360 / (n + 8)));
  const quiet = 2; // modules of quiet zone in the drawing
  const px = (n + quiet * 2) * cell;
  canvas.width = px;
  canvas.height = px;
  canvas.style.width = Math.min(px, 420) + "px";
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, px, px);
  const flips = new Set((opts.flips || []).map((f) => f[0] + "," + f[1]));
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const dark = rows[r][c] === "1";
      ctx.fillStyle = dark ? "#111" : "#fff";
      ctx.fillRect((c + quiet) * cell, (r + quiet) * cell, cell, cell);
      if (flips.has(r + "," + c)) {
        ctx.strokeStyle = dark ? "#f85149" : "#ff8b83";
        ctx.lineWidth = 2;
        ctx.strokeRect((c + quiet) * cell + 1, (r + quiet) * cell + 1, cell - 2, cell - 2);
      }
    }
  }
}

function cards(el, items) {
  el.innerHTML = "";
  for (const item of items) {
    const div = document.createElement("div");
    div.className = "card";
    const k = document.createElement("div");
    k.className = "k";
    k.textContent = item[0];
    const v = document.createElement("div");
    v.className = "v" + (item[2] ? " " + item[2] : "");
    v.textContent = item[1];
    div.appendChild(k);
    div.appendChild(v);
    el.appendChild(div);
  }
}

/* ------------------------------------------------------------- generate */

async function runGen() {
  const res = await api("/api/encode", {
    text: $("gen-text").value, level: $("gen-level").value,
  });
  if (res.error) { cards($("gen-cards"), [["错误", res.error, "bad"]]); return; }
  STATE.gen = res;
  drawMatrix($("gen-canvas"), res.rows);
  $("gen-matrix").textContent = res.rows.map((r) => r.split("").map((b) => b === "1" ? "##" : "  ").join("")).join("\n");
  cards($("gen-cards"), [
    ["版本", res.version + "-" + res.level],
    ["模式", res.mode],
    ["掩码", "mask " + res.mask],
    ["尺寸", res.size + " × " + res.size],
    ["数据块", res.blocks.join(" + ")],
    ["EC 码字/块", res.ec_len],
  ]);
}
$("gen-run").addEventListener("click", runGen);

/* ----------------------------------------------------------------- heal */

async function runHealEncode() {
  const res = await api("/api/encode", {
    text: $("heal-text").value, level: $("heal-level").value,
  });
  if (res.error) return;
  STATE.heal.base = res;
  STATE.heal.rows = res.rows;
  STATE.heal.flips = [];
  STATE.heal.seed = 0;
  applyDamage();
}

async function applyDamage() {
  const cells = STATE.heal.cells;
  const res = await api("/api/damage", {
    text: $("heal-text").value, level: $("heal-level").value,
    cells, seed: STATE.heal.seed,
  });
  if (res.error) return;
  drawMatrix($("heal-canvas"), res.rows, { flips: res.flips });
  const d = res.decoded;
  const box = $("heal-result");
  box.className = "result-box " + (d.ok ? "ok" : "err");
  box.innerHTML = "";
  const st = document.createElement("div");
  st.className = "status " + (d.ok ? "good" : "bad");
  st.textContent = d.ok
    ? `✓ 自愈成功：纠正 ${d.corrected_bytes} 字节（纠错级 ${d.level}，掩码 ${d.mask}）`
    : `✗ 超出纠错容量：${d.error || "部分块不可恢复"}`;
  const tx = document.createElement("div");
  tx.className = "text";
  tx.textContent = "解码文本: " + (d.ok ? d.text : "(无法恢复)");
  box.appendChild(st);
  box.appendChild(tx);
  cards($("heal-cards"), [
    ["翻转模块", String(cells)],
    ["纠正字节", String(d.corrected_bytes), d.ok ? "good" : "bad"],
    ["EC 容量/块", String(Math.floor(STATE.heal.base.ec_len / 2)) + " 字节"],
  ]);
}

$("heal-run").addEventListener("click", runHealEncode);
$("heal-slider").addEventListener("input", (e) => {
  STATE.heal.cells = Number(e.target.value);
  $("heal-slider-val").textContent = e.target.value;
  if (STATE.heal.base) applyDamage();
});
$("heal-seed").addEventListener("click", () => {
  STATE.heal.seed += 1;
  applyDamage();
});
$("heal-reset").addEventListener("click", () => {
  STATE.heal.seed = 0;
  STATE.heal.cells = 24;
  $("heal-slider").value = 24;
  $("heal-slider-val").textContent = "24";
  runHealEncode();
});

/* ----------------------------------------------------------------- mask */

function penaltyProxy(rows, mask) {
  /* Server computes real penalties; we ask it per mask via encode + decode
     is expensive, so the table is fetched from a dedicated endpoint. */
  return api("/api/encode", {
    text: $("mask-text").value,
    level: $("mask-level").value,
    mask: mask,
  });
}

async function runMask() {
  const res = await fetch("/api/masks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: $("mask-text").value, level: $("mask-level").value }),
  }).then((r) => r.json());
  if (res.error) return;
  drawMatrix($("mask-canvas"), res.rows);
  const tbl = $("mask-table");
  tbl.innerHTML = "";
  const head = document.createElement("tr");
  for (const h of ["掩码", "惩罚分", "N1", "N2", "N3", "N4", "选择"]) {
    const th = document.createElement("th");
    th.textContent = h;
    head.appendChild(th);
  }
  tbl.appendChild(head);
  for (const m of res.masks) {
    const tr = document.createElement("tr");
    if (m.id === res.best) tr.style.background = "#1a3a2a";
    for (const v of ["mask " + m.id, m.score, m.n1, m.n2, m.n3, m.n4,
                     m.id === res.best ? "★ 最低分" : ""]) {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    }
    tbl.appendChild(tr);
  }
  cards($("mask-cards"), [
    ["最优掩码", "mask " + res.best],
    ["惩罚分", String(res.score)],
    ["版本", res.version + "-" + res.level],
  ]);
}
$("mask-run").addEventListener("click", runMask);

/* ------------------------------------------------------------------- rs */

async function runRs() {
  const res = await fetch("/api/rs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: $("rs-text").value, level: $("rs-level").value }),
  }).then((r) => r.json());
  if (res.error) return;
  drawMatrix($("rs-canvas"), res.rows);
  const hex = (arr) => arr.map((b) => b.toString(16).padStart(2, "0").toUpperCase()).join(" ");
  const byCode = res.blocks.map(
    (b, i) => `block ${i} (${b.data.length}B data + ${b.ec.length}B ec)\n  data: ${hex(b.data)}\n  ec  : ${hex(b.ec)}`
  );
  const inter = `interleaved (${res.interleaved.length}B):\n${hex(res.interleaved)}`;
  $("rs-pipeline").textContent =
    `version ${res.version}-${res.level}  mode=${res.mode}  t=${res.t} bytes/block\n\n` +
    byCode.join("\n\n") + "\n\n" + inter;
  cards($("rs-cards"), [
    ["块数", String(res.blocks.length)],
    ["每块纠错", res.t + " 字节"],
    ["生成多项式", `g(x), ${res.ec_len} 次`],
    ["总码字", String(res.interleaved.length)],
  ]);
}
$("rs-run").addEventListener("click", runRs);

/* ---------------------------------------------------------------- bench */

async function runBench() {
  const res = await fetch("/api/bench", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: "{}" }).then((r) => r.json());
  const tbl = $("bench-table");
  tbl.innerHTML = "";
  const head = document.createElement("tr");
  for (const h of ["版本", "级别", "模式", "编码 ms", "解码 ms", "往返"]) {
    const th = document.createElement("th");
    th.textContent = h;
    head.appendChild(th);
  }
  tbl.appendChild(head);
  for (const row of res.rows) {
    const tr = document.createElement("tr");
    for (const v of [row.version + "-" + row.level, row.text.length + " 字符",
                     row.mode, row.enc_ms, row.dec_ms, row.ok ? "OK" : "FAIL"]) {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    }
    tbl.appendChild(tr);
  }
  $("bench-note").textContent = `共 ${res.rows.length} 组，平均编码 ${res.avg_enc} ms`;
}
$("bench-run").addEventListener("click", runBench);

/* ----------------------------------------------------------------- init */

async function initRef() {
  const info = await api("/api/info");
  const tbl = $("ref-table");
  tbl.innerHTML = "";
  const head = document.createElement("tr");
  for (const h of ["版本-级", "数据码字", "EC/块", "组1", "组2"]) {
    const th = document.createElement("th");
    th.textContent = h;
    head.appendChild(th);
  }
  tbl.appendChild(head);
  const keys = Object.keys(info.blocks).sort((a, b) => {
    const [va, la] = a.split("-"); const [vb, lb] = b.split("-");
    return va - vb || "LMQH".indexOf(la) - "LMQH".indexOf(lb);
  });
  for (const key of keys) {
    const [total, ec, g1n, g1d, g2n, g2d] = info.blocks[key];
    const tr = document.createElement("tr");
    for (const v of [key, total, ec, `${g1n}×${g1d}`, g2n ? `${g2n}×${g2d}` : "—"]) {
      const td = document.createElement("td");
      td.textContent = v;
      tr.appendChild(td);
    }
    tbl.appendChild(tr);
  }
}

initRef();
runGen();
runHealEncode();
