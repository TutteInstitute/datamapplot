// Re-embed engine: a classic Web Worker that runs UMAP (patched Rust/WASM
// build of umap-learn 0.6 from apple/embedding-atlas) on a precomputed kNN
// graph, starting from the points' current layout, and streams every epoch
// back to the page.
//
// This file is appended to the wasm-bindgen `no-modules` glue, which defines
// the global `wasm_bindgen`. The page posts the gzip-compressed WASM bytes, so
// the worker works from file://, notebook iframes and offline pages.

const MAX_EPOCHS_PER_SECOND = 60;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let state = { umap: null, paused: false, stopped: false, pendingParams: null, restart: false, idle: false };

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

/** Step along the optimizer's schedule to its horizon, pacing and posting every epoch. */
async function animate(phase, umap, n) {
  let t0 = performance.now();
  let epochsAtT0 = umap.epoch;
  let computeMs = 0;
  while (!state.stopped && (umap.epoch < umap.nEpochs || state.restart)) {
    if (state.restart) {
      state.restart = false;
      restartSchedule(phase, umap, n);
      postFrame(phase, umap, n, { restarted: true });
      t0 = performance.now();
      epochsAtT0 = umap.epoch;
      continue;
    }
    if (state.paused) {
      await sleep(50);
      t0 = performance.now();
      epochsAtT0 = umap.epoch;
      continue;
    }
    const allowed = epochsAtT0 + ((performance.now() - t0) / 1000) * MAX_EPOCHS_PER_SECOND;
    if (umap.epoch >= allowed) {
      await sleep(Math.max(1, ((umap.epoch - allowed + 1) / MAX_EPOCHS_PER_SECOND) * 1000));
      continue;
    }
    applyPendingParams(umap);
    const start = performance.now();
    await umap.stepScheduled(1);
    const elapsed = performance.now() - start;
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
  const engine = await loadEngine(msg.wasmGz, msg.engine);
  const { n, initXY, knnIdx, knnDist, sample } = msg;
  const options = (state.options = { ...msg.options, ...(state.pendingParams || {}) });
  state.pendingParams = null;
  state.full = { n, knnIdx, knnDist };
  state.engine = engine;
  // Engine status, with how long building the optimizer (graph + setup) took.
  const report = (umap, buildMs) =>
    self.postMessage({ type: "engine", ...engine, gpuActive: umap.gpuActive, gpuError: umap.gpuError ?? null, buildMs });

  if (!sample) {
    const t0 = performance.now();
    const umap = await buildUmap(n, knnIdx, knnDist, initXY, options, options.nEpochs, engine.gpuRequested);
    umap.setGoodInitialization(true);
    state.umap = umap;
    report(umap, performance.now() - t0);
    postFrame("full", umap, n, { initial: true });
    await animate("full", umap, n);
    finished(umap, n, "full");
    return;
  }

  // Large selection: animate a random sample, place the rest next to their
  // neighbours, then refine the whole set briefly.
  const m = sample.local.length;
  const sampleInit = new Float32Array(m * 2);
  for (let s = 0; s < m; s++) {
    sampleInit[2 * s] = initXY[2 * sample.local[s]];
    sampleInit[2 * s + 1] = initXY[2 * sample.local[s] + 1];
  }
  const t0 = performance.now();
  const sampleUmap = await buildUmap(m, sample.idx, sample.dist, sampleInit, options, options.nEpochs, engine.gpuRequested);
  sampleUmap.setGoodInitialization(true);
  state.umap = sampleUmap;
  report(sampleUmap, performance.now() - t0);
  postFrame("sample", sampleUmap, m, { initial: true });
  await animate("sample", sampleUmap, m);
  if (state.stopped) return;

  const tPlace = performance.now();
  const sampleEmbedding = readEmbedding(sampleUmap, m);
  sampleUmap.free();
  state.umap = null;
  const { pos, unplaced } = placeRest(n, sample.local, sampleEmbedding, knnIdx);
  state.pos = pos;
  self.postMessage({ type: "placed", embedding: pos.slice(), unplaced, placeMs: performance.now() - tPlace, runId: state.runId });

  if (options.refineEpochs > 0) {
    const tBuild = performance.now();
    const umap = await buildFull(pos, options.refineEpochs);
    report(umap, performance.now() - tBuild);
    await animate("refine", umap, n);
    finished(umap, n, "refine");
  } else {
    finished(null, n, "refine");
  }
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
      state = {
        umap: null, paused: !!msg.startPaused, stopped: false, pendingParams: null,
        restart: false, idle: false, runId: msg.runId,
      };
      await start(msg);
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
    }
  } catch (error) {
    self.postMessage({ type: "error", error: String((error && error.stack) || error) });
  }
};
