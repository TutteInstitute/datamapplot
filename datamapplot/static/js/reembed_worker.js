// Re-embed engine: a classic Web Worker that requests the kNN graph of a
// selection from the ReembedServer, runs UMAP on it (patched Rust/WASM build of
// umap-learn 0.6 from apple/embedding-atlas) starting from the points' current
// layout, and streams every epoch back to the page.
//
// Roles: "full" optimizes the selection; "sample" optimizes a random sample,
// paced to keep moving until the full optimizer is ready; "hold" requests the
// full graph (on "go") and builds its optimizer, then on "adopt" places the rest
// of the points next to the sample's layout and optimizes them all.
//
// This file is appended to the wasm-bindgen `no-modules` glue, which defines
// the global `wasm_bindgen`. The page posts the gzip-compressed WASM bytes, so
// the worker works from file://, notebook iframes and offline pages.

const MAX_EPOCHS_PER_SECOND = 60;
const MIN_EPOCHS_PER_SECOND = 6;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const newState = (extra = {}) => ({
  umap: null, paused: false, stopped: false, pendingParams: null, restart: false, idle: false,
  paceUntil: 0, ...extra,
});
let state = newState();

// ---------------------------------------------------------------- graph request

const part1by1 = (v) => {
  v = (v | (v << 8)) & 0x00ff00ff;
  v = (v | (v << 4)) & 0x0f0f0f0f;
  v = (v | (v << 2)) & 0x33333333;
  return (v | (v << 1)) & 0x55555555;
};

/**
 * Indices of the points in Z-order of their 2D positions: sent in this order, a
 * point's graph neighbours have nearby request positions, which the server
 * encodes compactly.
 */
function spatialOrder(P, n) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < n; i++) {
    x0 = Math.min(x0, P[2 * i]); x1 = Math.max(x1, P[2 * i]);
    y0 = Math.min(y0, P[2 * i + 1]); y1 = Math.max(y1, P[2 * i + 1]);
  }
  const scale = 16383 / Math.max(x1 - x0, y1 - y0, 1e-30);
  // Key = 28-bit Morton code * 2^24 + index: exact in a double for n < 2^24.
  const keys = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const code = part1by1(((P[2 * i] - x0) * scale) | 0) | (part1by1(((P[2 * i + 1] - y0) * scale) | 0) << 1);
    keys[i] = code * 16777216 + i;
  }
  keys.sort();
  const order = new Int32Array(n);
  for (let r = 0; r < n; r++) order[r] = keys[r] % 16777216;
  return order;
}

/** Decode a kNN array sent with encoding=varint (see encode_knn in reembed_server.py). */
function decodeKnn(a, bytes) {
  const [n, width] = a.shape;
  const offsets = a.encoding === "row-delta-varint";
  if (!offsets && a.encoding !== "step-varint") throw new Error("unknown array encoding " + a.encoding);
  const out = offsets ? new Int32Array(n * width) : new Float32Array(n * width);
  let p = 0;
  for (let i = 0; i < n; i++) {
    let q = 0;
    for (let c = 0; c < width; c++) {
      let v = 0, mul = 1, b;
      do { b = bytes[p++]; v += (b & 127) * mul; mul *= 128; } while (b & 128);
      if (offsets) out[i * width + c] = i + (v % 2 ? -(v + 1) / 2 : v / 2);
      else { q += v; out[i * width + c] = q * a.step; }
    }
  }
  return out;
}

/** Parse the ReembedServer binary response. */
function unpack(buffer) {
  const headLen = new DataView(buffer).getUint32(0, true);
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 4, headLen)));
  const base = 4 + headLen, arrays = {};
  for (const a of header.arrays) {
    if (a.encoding) {
      arrays[a.name] = decodeKnn(a, new Uint8Array(buffer, base + a.offset, a.bytes));
      continue;
    }
    const Type = a.dtype === "int32" ? Int32Array : Float32Array;
    arrays[a.name] = new Type(buffer.slice(base + a.offset, base + a.offset + a.bytes));
  }
  return { header, arrays };
}

/** Graph rows/indices in request order -> the caller's order, given request position -> index. */
function reorderKnn(idx, dist, order) {
  const n = order.length, width = idx.length / n;
  const I = new Int32Array(idx.length), D = new Float32Array(dist.length);
  for (let r = 0; r < n; r++) {
    const i = order[r];
    for (let c = 0; c < width; c++) {
      const j = idx[r * width + c];
      I[i * width + c] = j < 0 ? j : order[j];
      D[i * width + c] = dist[r * width + c];
    }
  }
  return { idx: I, dist: D };
}

/** Read a response body, posting download progress. */
async function readBody(resp) {
  const total = Number(resp.headers.get("Content-Length")) || 0;
  if (!resp.body || !total) return resp.arrayBuffer();
  let out = new Uint8Array(total), received = 0, posted = 0;
  const reader = resp.body.getReader();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (received + value.length > out.length) {
      const grown = new Uint8Array(2 * (received + value.length));
      grown.set(out.subarray(0, received));
      out = grown;
    }
    out.set(value, received);
    received += value.length;
    const now = performance.now();
    if (now - posted > 100) {
      posted = now;
      self.postMessage({ type: "progress", received, total, runId: state.runId });
    }
  }
  return received === out.length ? out.buffer : out.slice(0, received).buffer;
}

/**
 * Request the kNN graph of `ids` (P: their positions, for the spatial order)
 * and return it in the order of `ids`, with where the time went.
 */
async function fetchGraph(request, ids, P) {
  const n = ids.length;
  const t0 = performance.now();
  const order = n < 16777216 ? spatialOrder(P, n) : null;
  let body = ids;
  if (order) {
    body = new Int32Array(n);
    for (let r = 0; r < n; r++) body[r] = ids[order[r]];
  }
  const tSend = performance.now();
  const resp = await fetch(request.url, {
    method: "POST",
    body,
    headers: { "Content-Type": "application/octet-stream", ...(request.headers || {}) },
  });
  if (!resp.ok) throw new Error("server responded " + resp.status + ": " + (await resp.text()).slice(0, 200));
  const tHeaders = performance.now();
  self.postMessage({ type: "headers", runId: state.runId });
  // A sample tells the worker holding the full graph to request it (without waiting for the page).
  if (state.port) state.port.postMessage("go");
  const buffer = await readBody(resp);
  const tBody = performance.now();
  const { header, arrays } = unpack(buffer);
  let idx = arrays.knn_indices, dist = arrays.knn_distances;
  if (order) ({ idx, dist } = reorderKnn(idx, dist, order));
  const tDone = performance.now();
  // Upload and server times are measured by the server; "other" is latency
  // plus preparing and decoding here.
  const net = performance.getEntriesByName(resp.url).pop();
  const timing = {
    n,
    startedAt: performance.timeOrigin + t0,
    totalMs: tDone - t0,
    prepareMs: tSend - t0,
    firstByteMs: tHeaders - tSend,
    uploadMs: header.receiveSeconds != null ? 1000 * header.receiveSeconds : null,
    serverMs: 1000 * (header.serverSeconds ?? header.knnSeconds),
    knnMs: 1000 * header.knnSeconds,
    downloadMs: tBody - tHeaders,
    networkDownloadMs: net && net.responseEnd > 0 ? net.responseEnd - net.responseStart : null,
    decodeMs: tDone - tBody,
    uploadBytes: body.byteLength,
    downloadBytes: buffer.byteLength,
  };
  timing.otherMs = timing.totalMs - (timing.uploadMs || 0) - timing.serverMs - timing.downloadMs;
  return { idx, dist, header, timing };
}

// ---------------------------------------------------------------- engine

async function gunzip(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function loadEngine(wasmGz, engine) {
  await wasm_bindgen({ module_or_path: await gunzip(wasmGz) });
  let adapter = null;
  if (engine !== "cpu" && self.navigator.gpu) {
    try {
      adapter = await self.navigator.gpu.requestAdapter({ powerPreference: "high-performance" });
    } catch (error) {
      adapter = null;
    }
  }
  const info = adapter && adapter.info ? adapter.info : {};
  return {
    gpuRequested: engine === "gpu" || (engine === "auto" && !!adapter),
    adapter: adapter ? info.description || info.architecture || info.vendor || "available" : null,
  };
}

function buildUmap(n, knnIdx, knnDist, init, options, nEpochs, gpu) {
  let builder = new wasm_bindgen.UMAPFromKnnBuilder(knnIdx, knnDist, n, 2)
    .optimizer("adam")
    .compatibilityLayout(false)
    .initEmbedding(init)
    .initRescale(options.initRescale || "isotropic")
    .nEpochs(nEpochs)
    .randomState(BigInt(options.seed ?? 42))
    .minDist(options.minDist)
    .spread(options.spread)
    .repulsionStrength(options.repulsionStrength);
  if (gpu) builder = builder.gpu(true);
  return builder.build();
}

function readEmbedding(umap, n) {
  const out = new Float32Array(2 * n);
  umap.copyEmbeddingInto(out);
  return out;
}

function postFrame(phase, umap, n, extra = {}) {
  const embedding = readEmbedding(umap, n);
  self.postMessage(
    { type: "frame", phase, epoch: umap.epoch, nEpochs: umap.nEpochs, embedding, runId: state.runId, ...extra },
    [embedding.buffer],
  );
}

function applyPendingParams(umap) {
  const p = state.pendingParams;
  if (!p) return;
  state.pendingParams = null;
  Object.assign(state.options, p);
  // (learningRate, repulsionStrength, negativeSampleRate, minDist, spread); undefined = unchanged.
  umap.setParameters(undefined, p.repulsionStrength, undefined, p.minDist, p.spread);
}

/** Restart the annealing schedule from the current layout (after a parameter change). */
function restartSchedule(phase, umap, n) {
  applyPendingParams(umap);
  const embedding = readEmbedding(umap, n);
  umap.setNEpochs(phase === "refine" ? state.options.refineEpochs : state.options.nEpochs);
  umap.resetEmbedding(embedding, false);
  umap.setGoodInitialization(true);
}

/**
 * Epochs per second: at most 60, or spread over the time left when paced (see
 * "pace"); past the deadline as slow as allowed, to keep moving until relieved.
 */
function epochRate(umap) {
  if (!state.paceUntil) return MAX_EPOCHS_PER_SECOND;
  const left = (state.paceUntil - performance.now()) / 1000;
  const rate = left > 0 ? (umap.nEpochs - umap.epoch) / left : MIN_EPOCHS_PER_SECOND;
  return Math.min(MAX_EPOCHS_PER_SECOND, Math.max(MIN_EPOCHS_PER_SECOND, rate));
}

/** Step along the optimizer's schedule to its horizon, pacing and posting every epoch. */
async function animate(phase, umap, n) {
  let last = 0;
  let computeMs = 0;
  while (!state.stopped && (umap.epoch < umap.nEpochs || state.restart)) {
    if (state.restart) {
      state.restart = false;
      restartSchedule(phase, umap, n);
      postFrame(phase, umap, n, { restarted: true });
      continue;
    }
    if (state.paused) {
      await sleep(50);
      continue;
    }
    const wait = last + 1000 / epochRate(umap) - performance.now();
    if (wait > 1) {
      await sleep(Math.min(wait, 100));
      continue;
    }
    last = performance.now();
    applyPendingParams(umap);
    await umap.stepScheduled(1);
    const elapsed = performance.now() - last;
    computeMs = computeMs ? 0.8 * computeMs + 0.2 * elapsed : elapsed;
    postFrame(phase, umap, n, { computeMs });
  }
}

/** Place each non-sample point at the mean of its already-placed kNN neighbours (iterated). */
function placeRest(n, sampleLocal, sampleEmbedding, knnIdx) {
  const width = knnIdx.length / n;
  const pos = new Float32Array(n * 2);
  const placed = new Uint8Array(n);
  for (let s = 0; s < sampleLocal.length; s++) {
    const i = sampleLocal[s];
    pos[2 * i] = sampleEmbedding[2 * s];
    pos[2 * i + 1] = sampleEmbedding[2 * s + 1];
    placed[i] = 1;
  }
  let remaining = n - sampleLocal.length;
  for (let pass = 0; pass < 10 && remaining > 0; pass++) {
    const newly = [];
    for (let i = 0; i < n; i++) {
      if (placed[i]) continue;
      let sx = 0, sy = 0, c = 0;
      for (let j = 0; j < width; j++) {
        const nb = knnIdx[i * width + j];
        if (nb !== i && placed[nb]) {
          sx += pos[2 * nb];
          sy += pos[2 * nb + 1];
          c++;
        }
      }
      if (c > 0) newly.push([i, sx / c, sy / c]);
    }
    if (!newly.length) break;
    for (const [i, x, y] of newly) {
      pos[2 * i] = x;
      pos[2 * i + 1] = y;
      placed[i] = 1;
    }
    remaining -= newly.length;
  }
  if (remaining > 0) {
    let cx = 0, cy = 0;
    for (let s = 0; s < sampleLocal.length; s++) {
      cx += sampleEmbedding[2 * s];
      cy += sampleEmbedding[2 * s + 1];
    }
    cx /= sampleLocal.length;
    cy /= sampleLocal.length;
    for (let i = 0; i < n; i++) {
      if (!placed[i]) {
        pos[2 * i] = cx;
        pos[2 * i + 1] = cy;
      }
    }
  }
  return { pos, unplaced: remaining };
}

/** Report that the current run finished; the worker then idles, keeping the optimizer for re-runs. */
function finished(umap, n, phase) {
  if (state.stopped) return;
  state.umap = umap;
  state.n = n;
  state.phase = phase;
  state.idle = true;
  self.postMessage({ type: "done", runId: state.runId });
}

async function start(msg) {
  const { n, initXY, role } = msg;
  state.options = { ...msg.options, ...(state.pendingParams || {}) };
  state.pendingParams = null;
  // Load the engine while the graph is requested.
  const loading = loadEngine(msg.wasmGz, msg.engine);
  loading.catch(() => {});
  let graph = msg.graph;
  if (!graph) {
    if (msg.request.deferred) await state.go;
    if (state.stopped) return;
    graph = await fetchGraph(msg.request, msg.ids, initXY);
    if (state.stopped) return;
    // The page keeps the full graph to re-optimize the level later without a request.
    const keep = role === "sample" ? {} : { idx: graph.idx.slice(), dist: graph.dist.slice() };
    self.postMessage({ type: "graph", timing: graph.timing, runId: state.runId, ...keep });
  }
  const engine = (state.engine = await loading);
  state.full = { n, knnIdx: graph.idx, knnDist: graph.dist };
  const options = state.options;
  // Engine status, with how long building the optimizer (graph + setup) took.
  const report = (umap, buildMs) => self.postMessage({
    type: "engine", ...engine, gpuActive: umap.gpuActive, gpuError: umap.gpuError ?? null, buildMs, n, runId: state.runId,
  });
  const t0 = performance.now();
  const umap = await buildUmap(n, graph.idx, graph.dist, initXY, options, options.nEpochs, engine.gpuRequested);
  umap.setGoodInitialization(true);
  state.umap = umap;
  report(umap, performance.now() - t0);
  if (state.stopped) return;

  if (role === "hold") {
    self.postMessage({ type: "ready", runId: state.runId });
    const { sampleLocal, sampleEmbedding } = await state.adopt;
    if (state.stopped) return;
    if (sampleEmbedding) {
      const tPlace = performance.now();
      const { pos, unplaced } = placeRest(n, sampleLocal, sampleEmbedding, graph.idx);
      state.pos = pos;
      self.postMessage({ type: "placed", embedding: pos.slice(), unplaced, placeMs: performance.now() - tPlace, runId: state.runId });
      // Continue in the sample's coordinate frame (no rescale), so the page's display mapping still applies.
      state.restart = false;
      applyPendingParams(umap);
      umap.resetEmbedding(pos, false);
      umap.setGoodInitialization(true);
      umap.setParameters(0.5, undefined, undefined, undefined, undefined);
      umap.setNEpochs(state.options.refineEpochs);
      await animate("refine", umap, n);
      finished(umap, n, "refine");
      return;
    }
  }
  const phase = role === "sample" ? "sample" : "full";
  postFrame(phase, umap, n, { initial: true });
  await animate(phase, umap, n);
  finished(umap, n, phase);
}

/**
 * Optimizer for the whole selection, continuing in the current coordinate frame
 * (no rescale) so the page's display mapping still applies.
 */
async function buildFull(pos, nEpochs) {
  const { n, knnIdx, knnDist } = state.full;
  const umap = await buildUmap(n, knnIdx, knnDist, pos, state.options, nEpochs, state.engine.gpuRequested);
  umap.resetEmbedding(pos, false);
  umap.setGoodInitialization(true);
  umap.setParameters(0.5, undefined, undefined, undefined, undefined);
  state.umap = umap;
  return umap;
}

/** Re-optimize the whole selection from its current layout after a parameter change. */
async function relax() {
  let umap = state.umap;
  if (!umap) umap = await buildFull(state.pos, state.options.nEpochs);
  state.restart = true;
  await animate("relax", umap, state.n);
  finished(umap, state.n, "relax");
}

self.onmessage = async (event) => {
  const msg = event.data;
  try {
    if (msg.cmd === "start") {
      let go, adopt;
      state = newState({ paused: !!msg.startPaused, runId: msg.runId, port: msg.port || null });
      state.go = new Promise((resolve) => (go = resolve));
      if (state.port && msg.role === "hold") state.port.onmessage = () => go();
      state.adopt = new Promise((resolve) => (adopt = resolve));
      state.resolveGo = go;
      state.resolveAdopt = adopt;
      await start(msg);
    } else if (msg.cmd === "go") {
      state.resolveGo();
    } else if (msg.cmd === "adopt") {
      state.paused = !!msg.paused;
      state.resolveAdopt(msg);
    } else if (msg.cmd === "pace") {
      state.paceUntil = performance.now() + msg.ms;
    } else if (msg.cmd === "pause") {
      state.paused = true;
    } else if (msg.cmd === "resume") {
      state.paused = false;
    } else if (msg.cmd === "params") {
      // New parameters restart the schedule from the current layout: immediately
      // if a run is in progress, or as a new run if the worker is idle.
      state.pendingParams = { ...(state.pendingParams || {}), ...msg.params };
      state.runId = msg.runId;
      if (state.options) {
        state.restart = true;
        if (state.idle) {
          state.idle = false;
          await relax();
        }
      }
    } else if (msg.cmd === "stop") {
      state.stopped = true;
      if (state.resolveGo) state.resolveGo();
      if (state.resolveAdopt) state.resolveAdopt({});
    }
  } catch (error) {
    self.postMessage({ type: "error", error: String((error && error.stack) || error) });
  }
};
