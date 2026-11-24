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

let state = { umap: null, paused: false, stopped: false, pendingParams: null };

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
    { type: "frame", phase, epoch: umap.epoch, nEpochs: umap.nEpochs, embedding, ...extra },
    [embedding.buffer],
  );
}

function applyPendingParams(umap) {
  const p = state.pendingParams;
  if (!p) return;
  state.pendingParams = null;
  // (learningRate, repulsionStrength, negativeSampleRate, minDist, spread); undefined = unchanged.
  umap.setParameters(undefined, p.repulsionStrength, undefined, p.minDist, p.spread);
}

/** Step along the optimizer's schedule to its horizon, pacing and posting every epoch. */
async function animate(phase, umap, n) {
  let t0 = performance.now();
  let epochsAtT0 = umap.epoch;
  let computeMs = 0;
  while (!state.stopped && umap.epoch < umap.nEpochs) {
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

async function start(msg) {
  const engine = await loadEngine(msg.wasmGz, msg.engine);
  const { n, initXY, knnIdx, knnDist, sample, options } = msg;
  const report = (umap) =>
    self.postMessage({ type: "engine", ...engine, gpuActive: umap.gpuActive, gpuError: umap.gpuError ?? null });

  if (!sample) {
    const t0 = performance.now();
    const umap = await buildUmap(n, knnIdx, knnDist, initXY, options, options.nEpochs, engine.gpuRequested);
    umap.setGoodInitialization(true);
    state.umap = umap;
    report(umap);
    postFrame("full", umap, n, { initial: true, buildMs: performance.now() - t0 });
    await animate("full", umap, n);
    if (!state.stopped) self.postMessage({ type: "done" });
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
  report(sampleUmap);
  postFrame("sample", sampleUmap, m, { initial: true, buildMs: performance.now() - t0 });
  await animate("sample", sampleUmap, m);
  if (state.stopped) return;

  const tPlace = performance.now();
  const sampleEmbedding = readEmbedding(sampleUmap, m);
  sampleUmap.free();
  state.umap = null;
  const { pos, unplaced } = placeRest(n, sample.local, sampleEmbedding, knnIdx);
  self.postMessage({ type: "placed", embedding: pos, unplaced, placeMs: performance.now() - tPlace });

  if (options.refineEpochs > 0) {
    // Continue in the sample run's coordinate frame (no rescale) so the page's
    // display mapping still applies.
    const umap = await buildUmap(n, knnIdx, knnDist, pos, options, options.refineEpochs, engine.gpuRequested);
    umap.resetEmbedding(pos, false);
    umap.setGoodInitialization(true);
    umap.setParameters(0.5, undefined, undefined, undefined, undefined);
    state.umap = umap;
    report(umap);
    await animate("refine", umap, n);
  }
  if (!state.stopped) self.postMessage({ type: "done" });
}

self.onmessage = async (event) => {
  const msg = event.data;
  try {
    if (msg.cmd === "start") {
      state = { umap: null, paused: !!msg.startPaused, stopped: false, pendingParams: null };
      await start(msg);
    } else if (msg.cmd === "pause") {
      state.paused = true;
    } else if (msg.cmd === "resume") {
      state.paused = false;
    } else if (msg.cmd === "params") {
      state.pendingParams = { ...(state.pendingParams || {}), ...msg.params };
    } else if (msg.cmd === "stop") {
      state.stopped = true;
    }
  } catch (error) {
    self.postMessage({ type: "error", error: String((error && error.stack) || error) });
  }
};
