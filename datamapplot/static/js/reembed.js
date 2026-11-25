/**
 * ReembedWidget: lasso a region of the map and re-run UMAP on just those
 * points, live in the browser, starting from their current positions.
 *
 * - The kNN graph of the selection comes from a ReembedServer (Python).
 * - UMAP (Rust/WASM, optionally WebGPU) runs in a Web Worker whose source and
 *   WASM bytes are inlined in the page; every epoch is animated.
 * - Re-embeds can be nested; Back animates out again.
 *
 * While a re-embedding is shown, the DataMap's own point layer and all other
 * layers are hidden with a deck.gl `layerFilter`, and the re-embedded points
 * are drawn by layers with ids starting with "reembed-" that live in
 * `datamap.layers` (so DataMap's own layer updates keep them).
 */
const ReembedWidget = (() => {
  const T = {
    PREFADE_MS: 220, ZOOM_MS: 1100, BACK_MS: 1100, FADEIN_MS: 300, SEL_MS: 250, FADE_MS: 600,
    FIT_FILL: 0.84, FIT_SAMPLE: 4096, HOME_FILL: 0.85, MAX_PX: 6,
    TAU_OUT: 0.35, TAU_IN: 1.2, MIN_POINTS: 50, LABEL_SAMPLE: 96,
  };
  const OURS = "reembed-";
  const IDENTITY_MAP = { scale: 1, xc: 0, yc: 0, hx: 0, hy: 0 };
  const isOurs = (layer) => layer.id.startsWith(OURS);
  const isPoints = (layer) => layer.id.startsWith("dataPointLayer");

  // ---------------------------------------------------------------- helpers
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smoothstep = (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));

  // Web Mercator (deck.gl MapView): world coordinates in radians.
  // Browsers can expose WebGPU without a usable adapter (headless, blocklisted GPUs).
  let gpuProbe = null;
  const gpuAvailable = () => (gpuProbe = gpuProbe || (navigator.gpu
    ? navigator.gpu.requestAdapter({ powerPreference: "high-performance" }).then((a) => !!a, () => false)
    : Promise.resolve(false)));

  const D2R = Math.PI / 180;
  const mercY = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * D2R) / 2));
  const invMercY = (y) => (2 * Math.atan(Math.exp(y)) - Math.PI / 2) / D2R;
  const pxPerRad = (zoom) => (512 * 2 ** zoom) / (2 * Math.PI);

  /** Least-squares Y ≈ s·X + t (uniform scale + translation). */
  function fitSimilarity(X, Y) {
    const n = X.length / 2;
    let mx = 0, my = 0, ux = 0, uy = 0;
    for (let i = 0; i < n; i++) { mx += X[2 * i]; my += X[2 * i + 1]; ux += Y[2 * i]; uy += Y[2 * i + 1]; }
    mx /= n; my /= n; ux /= n; uy /= n;
    let num = 0, den = 0;
    for (let i = 0; i < n; i++) {
      const ax = X[2 * i] - mx, ay = X[2 * i + 1] - my;
      num += ax * (Y[2 * i] - ux) + ay * (Y[2 * i + 1] - uy);
      den += ax * ax + ay * ay;
    }
    const s = den > 0 ? num / den : 1;
    return { s, tx: ux - s * mx, ty: uy - s * my };
  }

  function gather(src, idx, width) {
    const out = new src.constructor(idx.length * width);
    for (let t = 0; t < idx.length; t++) {
      for (let c = 0; c < width; c++) out[width * t + c] = src[width * idx[t] + c];
    }
    return out;
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

  const part1by1 = (v) => {
    v = (v | (v << 8)) & 0x00ff00ff;
    v = (v | (v << 4)) & 0x0f0f0f0f;
    v = (v | (v << 2)) & 0x33333333;
    return (v | (v << 1)) & 0x55555555;
  };

  /**
   * Local indices in Z-order of their 2D positions: sent in this order, a point's
   * graph neighbours have nearby request positions, which the server encodes compactly.
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

  /** Graph rows/indices in request order -> local order, given request position -> local index. */
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

  /** Positions that appear on screen under view `to` exactly where `P` appears under view `from`. */
  function reexpress(P, from, to, out = new Float32Array(P.length)) {
    const r = 2 ** (from.zoom - to.zoom);
    const fy = mercY(from.latitude), ty = mercY(to.latitude);
    for (let i = 0; i < P.length; i += 2) {
      out[i] = to.longitude + (P[i] - from.longitude) * r;
      out[i + 1] = invMercY(ty + (mercY(P[i + 1]) - fy) * r);
    }
    return out;
  }

  /** Evenly strided sample of indices, for cheap robust bounds every frame. */
  function sampleIndices(n, k = T.FIT_SAMPLE) {
    const m = Math.min(n, k), out = new Int32Array(m);
    for (let j = 0; j < m; j++) out[j] = Math.floor(((j + 0.5) * n) / m);
    return out;
  }

  /** [lon0, lon1, lat0, lat1] from quantiles of a sample (ignores outliers), with a margin. */
  function robustBounds(P, sample, alpha = null, q = 0.005) {
    const xs = new Float32Array(sample.length), ys = new Float32Array(sample.length);
    let m = 0;
    for (const i of sample) {
      if (alpha && alpha[i] < 0.01) continue;
      xs[m] = P[2 * i]; ys[m] = P[2 * i + 1]; m++;
    }
    if (!m) return null;
    const sx = xs.subarray(0, m).sort(), sy = ys.subarray(0, m).sort();
    const lo = (v) => v[Math.floor(q * (m - 1))], hi = (v) => v[Math.ceil((1 - q) * (m - 1))];
    const x0 = lo(sx), x1 = hi(sx), y0 = lo(sy), y1 = hi(sy);
    const mx = 0.04 * Math.max(x1 - x0, 1e-6), my = 0.04 * Math.max(y1 - y0, 1e-6);
    return [x0 - mx, x1 + mx, y0 - my, y1 + my];
  }

  /** Camera that fits bounds into a viewport (exact Web Mercator). */
  function fitView(b, size, fill = T.FIT_FILL) {
    const dx = Math.max((b[1] - b[0]) * D2R, 1e-9);
    const y0 = mercY(b[2]), y1 = mercY(b[3]), dy = Math.max(y1 - y0, 1e-9);
    const ppr = Math.min((size.width * fill) / dx, (size.height * fill) / dy);
    return {
      longitude: (b[0] + b[1]) / 2, latitude: invMercY((y0 + y1) / 2),
      zoom: Math.log2((ppr * 2 * Math.PI) / 512), pitch: 0, bearing: 0,
    };
  }

  function medianOf(values, sample) {
    const v = Float32Array.from(sample, (i) => values[i]).sort();
    return v.length ? v[v.length >> 1] : 1;
  }

  /**
   * Smooth "camera-like" tween from P0 to P1: the best-fit similarity is
   * interpolated with exponential scale about its fixed point (constant
   * perceived zoom speed), plus a linearly blended residual.
   */
  function zoomTween(P0, P1) {
    const f = fitSimilarity(P0, P1);
    const linear = Math.abs(f.s - 1) < 1e-3;
    const k = linear ? 1 : f.s;
    const cx = linear ? 0 : f.tx / (1 - f.s), cy = linear ? 0 : f.ty / (1 - f.s);
    const R = new Float32Array(P0.length);
    for (let i = 0; i < P0.length; i += 2) {
      R[i] = P1[i] - (cx + (P0[i] - cx) * k);
      R[i + 1] = P1[i + 1] - (cy + (P0[i + 1] - cy) * k);
    }
    return { P0, R, k, cx, cy };
  }

  /** A tween of other points that follows the same zoom (no residual). */
  const followTween = (P0, tw) => ({ P0, R: null, k: tw.k, cx: tw.cx, cy: tw.cy });

  function tweenAt(tw, e, out) {
    const kk = tw.k ** e, { P0, R, cx, cy } = tw;
    for (let i = 0; i < P0.length; i += 2) {
      out[i] = cx + (P0[i] - cx) * kk + (R ? e * R[i] : 0);
      out[i + 1] = cy + (P0[i + 1] - cy) * kk + (R ? e * R[i + 1] : 0);
    }
  }

  /**
   * Put each label at an approximate medoid of its members' positions `P`: the
   * member (of a fixed strided sample) nearest the coordinate-wise median.
   */
  const labelXs = new Float32Array(T.LABEL_SAMPLE), labelYs = new Float32Array(T.LABEL_SAMPLE);
  function placeLabels(items, P) {
    for (const item of items) {
      const sample = item._sample, m = sample.length;
      for (let j = 0; j < m; j++) {
        labelXs[j] = P[2 * sample[j]];
        labelYs[j] = P[2 * sample[j] + 1];
      }
      const mx = labelXs.subarray(0, m).sort()[m >> 1], my = labelYs.subarray(0, m).sort()[m >> 1];
      let best = Infinity;
      for (let j = 0; j < m; j++) {
        const x = P[2 * sample[j]], y = P[2 * sample[j] + 1];
        const d = (x - mx) ** 2 + (y - my) ** 2;
        if (d < best) {
          best = d;
          item.x = x;
          item.y = y;
        }
      }
    }
  }

  /** Opacity factor of a DataMap selection value (mirrors its DataFilterExtension soft range, which uses smoothstep). */
  const selectionFactor = (v) => {
    const t = clamp((v + 0.5) / 1.25, 0, 1);
    return t * t * (3 - 2 * t);
  };

  /** Two alternating typed arrays, so deck.gl sees a new array whenever content changes. */
  class DoubleBuffer {
    constructor(Type, length) { this.bufs = [new Type(length), new Type(length)]; this.i = 0; }
    next() { this.i ^= 1; return this.bufs[this.i]; }
  }

  // ---------------------------------------------------------------- controller
  class ReembedController {
    constructor(datamap, config, ui) {
      this.dm = datamap;
      this.cfg = config;
      this.ui = ui;
      gpuAvailable();                // resolved by the first request
      this.levels = [];
      this.mode = "idle";            // idle | entering | running | back
      this.tr = null;                // active transition
      this.ft = null;                // tween between optimizer frames
      this.ghost = null;             // parent's other points during transitions
      this.labels = null;            // {items, opacity}: labels of the shown level
      this.ghostLabels = null;       // {items, opacity}: labels of the parent during transitions
      this.view = null;
      this.autofit = false;
      this.worker = null;
      this.runId = 0;                // bumped per optimizer run / parameter restart
      this.relaxing = false;         // re-optimizing after a parameter change
      this.map = null;               // optimizer coords -> display coords
      this.interArrival = 16;
      this.lastArrival = 0;
      this.lastTick = performance.now();
      this.lastCounter = -1;
      this.colorSource = null;
      this.filterMode = "none";
      this.selectionCount = 0;
      this.status = { phase: "", epoch: 0, nEpochs: 0, computeMs: 0, timing: null, buildMs: 0, engine: null, error: null };
      this.dm.onViewStateChange("reembed", (params) => this._onViewState(params));
      this.dm.pickRemap = (info) => this._remapPick(info);
      this.server = null;            // {stage, error} from /api/info
      this._pollServer();
      requestAnimationFrame(() => this._tick());
    }

    _serverBase() {
      return (this.cfg.server_url || (location.protocol.startsWith("http") ? location.origin : "")).replace(/\/$/, "");
    }

    /** Poll /api/info until the server is ready, so the widget can say what it is waiting for. */
    async _pollServer() {
      const base = this._serverBase();
      if (!base) return;
      let delay = 1000;
      for (;;) {
        try {
          const resp = await fetch(base + "/api/info", { headers: { ...(this.cfg.auth_headers || {}) } });
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          const info = await resp.json();
          this.server = { stage: info.stage || (info.ready && info.globalGraphReady ? "ready" : "warming up") };
          delay = 1000;
        } catch (error) {
          this.server = { stage: "unreachable", error: String(error.message || error) };
          delay = Math.min(2 * delay, 10000);
        }
        this.ui.update();
        if (this.server.stage === "ready") return;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    serverText() {
      const sv = this.server;
      if (!sv || sv.stage === "ready") return "";
      if (sv.stage === "unreachable") return "Re-embed server not reachable at " + this._serverBase() + ".";
      if (sv.stage === "warming up") return "Server warming up (compiling kNN code, ~20 s after it starts)…";
      return "Server " + sv.stage + "…";
    }

    // ---------------------------------------------------------------- levels
    current() { return this.levels[this.levels.length - 1]; }
    get depth() { return this.levels.length - 1; }

    _root() {
      if (this.levels.length) return this.levels[0];
      const attrs = this.dm.pointLayer.props.data.attributes;
      const pos = attrs.getPosition.value;
      const n = pos.length / 2;
      const fitIdx = sampleIndices(n);
      const b = robustBounds(pos, fitIdx);
      const radii = attrs.getRadius ? attrs.getRadius.value : null;
      const root = {
        ids: null, n, pos, fitIdx, radii, view: null, rs: 1,
        rMed: radii ? medianOf(radii, fitIdx) : this.dm.pointSize,
        homeCenter: [(b[0] + b[1]) / 2, (b[2] + b[3]) / 2],
        homeExtent: Math.max(b[1] - b[0], b[3] - b[2]),
        homeZoom: fitView(b, this._viewportSize()).zoom,
      };
      this.levels = [root];
      return root;
    }

    _viewportSize() {
      const vp = this.dm.deckgl.viewManager && this.dm.deckgl.viewManager.getViewports()[0];
      if (vp) return { width: vp.width, height: vp.height };
      return { width: this.dm.container.clientWidth, height: this.dm.container.clientHeight };
    }

    _currentView() {
      // The live viewport is authoritative: deck's internal view state mixes stale
      // top-level fields with per-view entries after user interaction.
      const vp = this.dm.deckgl.viewManager && this.dm.deckgl.viewManager.getViewports()[0];
      const v = vp || this.view || this.dm.deckgl.props.initialViewState;
      return { longitude: v.longitude, latitude: v.latitude, zoom: v.zoom, pitch: 0, bearing: 0 };
    }

    _setView(v) {
      this.view = { ...(this.view || this._currentView()), ...v };
      this.dm.deckgl.setProps({ initialViewState: { ...this.view } });
    }

    _onViewState({ viewState, interactionState }) {
      if (!viewState) return;
      this.view = { longitude: viewState.longitude, latitude: viewState.latitude, zoom: viewState.zoom, pitch: 0, bearing: 0 };
      if (interactionState && (interactionState.isDragging || interactionState.isPanning || interactionState.isZooming)) {
        if (this.depth > 0) this.current().userCamera = true;
        if (this.autofit && this.depth > 0) this.current().rs = this.rs;
        this.autofit = false;
      }
    }

    _remapPick(info) {
      if (info && info.layer && info.layer.id === OURS + "active" && info.index >= 0) {
        const level = this.current();
        if (level.ids) return { ...info, index: level.ids[info.index] };
      }
      return info;
    }

    /** Colours of every point currently used by the DataMap (respects colormap switching). */
    _baseColors() { return this.dm.pointLayer.props.data.attributes.getFillColor.value; }

    /**
     * Labels of the full map whose member points lie in `level` (at least the
     * `label_containment` fraction of them), sharing the map's label styling.
     */
    _levelLabels(level) {
      if (level.labels) return level.labels;
      const items = [];
      const dm = this.dm;
      const all = dm.labelLayer && this.cfg.show_labels !== false ? dm._allLabelData || dm.labelLayer.props.data : null;
      if (all && level.ids) {
        const minFraction = this.cfg.label_containment ?? 1;
        for (const d of all) {
          const related = d.relatedPoints;
          if (!related || !related.length) continue;
          let inside = 0;
          for (const g of related) if (level.local[g] >= 0) inside++;
          if (!inside || inside < minFraction * related.length) continue;
          const members = new Int32Array(inside);
          let t = 0;
          for (const g of related) if (level.local[g] >= 0) members[t++] = level.local[g];
          const m = Math.min(inside, T.LABEL_SAMPLE);
          const item = Object.create(d);  // keeps the label's own fields for the cloned accessors
          item._sample = Int32Array.from({ length: m }, (_, j) => members[Math.floor(((j + 0.5) * inside) / m)]);
          items.push(item);
        }
      }
      level.labels = items;
      return items;
    }

    _labelLayer(id, labels, positions) {
      placeLabels(labels.items, positions);
      return this.dm.labelLayer.clone({
        id, data: labels.items, opacity: labels.opacity, pickable: false,
        collisionGroup: id,  // independent of the map's (hidden) labels and of each other
        updateTriggers: { getPosition: this.version },
      });
    }

    /** Make `level` the displayed level at positions `pos` (copied). */
    _showLevel(level, pos, labelOpacity = 1) {
      const n = level.n;
      this.disp = Float32Array.from(pos);
      this.labels = { items: this._levelLabels(level), opacity: labelOpacity };
      this.posBuf = new DoubleBuffer(Float32Array, 2 * n);
      this.colorBuf = new DoubleBuffer(Uint8Array, 4 * n);
      this.colors = this.colorBuf.next();
      this.rgba = gather(this._baseColors(), level.ids, 4);
      this.colorSource = this._baseColors();
      this.alpha = new Float32Array(n).fill(1);
      this.visTarget = new Float32Array(n).fill(1);
      this.selTarget = new Float32Array(n).fill(1);
      this.alphaTween = null;
      this.colorsDirty = true;
      this.ft = null;
      this.target = null;
      this.lastCounter = -1;
    }

    // ---------------------------------------------------------------- layers
    _setFilter(mode) {
      if (mode === this.filterMode) return;
      this.filterMode = mode;
      const filter = mode === "none" ? null
        : mode === "points" ? ({ layer }) => !isPoints(layer)
        : ({ layer }) => isOurs(layer);
      this.dm.deckgl.setProps({ layerFilter: filter });
    }

    /** Replace layers via `fn`, keeping DataMap's own references to them up to date. */
    _mapLayers(fn) {
      const swaps = new Map();
      const next = this.dm.layers.map((layer) => {
        const out = fn(layer);
        if (out !== layer) swaps.set(layer, out);
        return out;
      });
      if (!swaps.size) return;
      this.dm.layers = next;
      for (const key of Object.keys(this.dm)) {
        const value = this.dm[key];
        if (value && swaps.has(value)) {
          this.dm[key] = swaps.get(value);
        } else if (Array.isArray(value) && value.length && value[0] instanceof deck.Layer && key !== "layers") {
          this.dm[key] = value.map((layer) => swaps.get(layer) || layer);
        }
      }
    }

    _captureOthers() {
      this.othersBase = new Map();
      for (const layer of this.dm.layers) {
        if (!isOurs(layer) && !isPoints(layer)) this.othersBase.set(layer.id, layer.props.opacity ?? 1);
      }
    }

    /** Scale the opacity of every non-point DataMap layer; layers created since the capture stay hidden. */
    _setOthersOpacity(f) {
      this._mapLayers((layer) => {
        if (isOurs(layer) || isPoints(layer)) return layer;
        const opacity = (this.othersBase.get(layer.id) ?? 0) * f;
        return layer.props.opacity === opacity ? layer : layer.clone({ opacity });
      });
    }

    _putLayers(layers) {
      const base = this.dm.layers.filter((layer) => !isOurs(layer));
      let at = base.findIndex(isPoints);
      if (at < 0) at = base.length;
      this.dm.layers = [...base.slice(0, at), ...layers, ...base.slice(at)];
      this.dm.deckgl.setProps({ layers: this.dm.layers });
    }

    _scatter(id, n, positions, colors, radii, { rs, minPx, opacity = 1, pickable = false, version = 0 }) {
      const dm = this.dm;
      const attributes = { getPosition: { value: positions, size: 2 }, getFillColor: { value: colors, size: 4 } };
      if (radii) attributes.getRadius = { value: radii, size: 1 };
      return new deck.ScatterplotLayer({
        id, data: { length: n, attributes },
        ...(radii ? {} : { getRadius: dm.pointSize }),
        radiusUnits: "common", radiusScale: rs,
        radiusMinPixels: minPx, radiusMaxPixels: dm.pointRadiusMaxPixels,
        stroked: true, getLineColor: dm.pointOutlineColor, getLineWidth: dm.pointLineWidth,
        lineWidthUnits: "common", lineWidthScale: rs,
        lineWidthMinPixels: dm.pointLineWidthMinPixels * Math.min(1, minPx / Math.max(dm.pointRadiusMinPixels, 1e-6)),
        lineWidthMaxPixels: dm.pointLineWidthMaxPixels,
        opacity, pickable, autoHighlight: pickable, highlightColor: dm.pointHoverColor,
        updateTriggers: { getPosition: version, getFillColor: version },
        parameters: { depthTest: false },
      });
    }

    _render() {
      this.version = (this.version || 0) + 1;
      const layers = [];
      const g = this.ghost;
      if (g && g.opacity > 0.002) {
        layers.push(this._scatter(OURS + "ghost", g.n, g.pos, g.rgba, g.radii,
          { rs: g.rs, minPx: g.minPx, opacity: g.opacity, version: this.version }));
      }
      const level = this.current();
      if (level && level.ids) {
        if (this.colorsDirty) {
          this.colors = this.colorBuf.next();
          for (let i = 0; i < level.n; i++) {
            this.colors[4 * i] = this.rgba[4 * i];
            this.colors[4 * i + 1] = this.rgba[4 * i + 1];
            this.colors[4 * i + 2] = this.rgba[4 * i + 2];
            this.colors[4 * i + 3] = Math.round(this.rgba[4 * i + 3] * this.alpha[i]);
          }
          this.colorsDirty = false;
        }
        const out = this.posBuf.next();
        out.set(this.disp);
        layers.push(this._scatter(OURS + "active", level.n, out, this.colors, level.radii, {
          rs: this.rs, minPx: this.minPx, opacity: this.opacity, pickable: this.mode === "idle", version: this.version,
        }));
      }
      const gl = this.ghostLabels;
      if (gl && g && gl.items.length && gl.opacity > 0.01) layers.push(this._labelLayer(OURS + "labels-ghost", gl, g.pos));
      const ll = this.labels;
      if (ll && level && level.ids && ll.items.length && ll.opacity > 0.01) layers.push(this._labelLayer(OURS + "labels", ll, this.disp));
      this._putLayers(layers);
    }

    // ---------------------------------------------------------------- selection & colours
    _syncSelection() {
      const counter = this.dm.updateTriggerCounter;
      if (counter === this.lastCounter || !this.dm.selected) return;
      this.lastCounter = counter;
      const level = this._root() && this.current();
      const lasso = this.dm.dataSelectionManager.hasSpecialSelection();
      const selected = this.dm.getSelectedIndices();
      if (!level.ids) {
        this.selectionCount = lasso ? selected.size : 0;
      } else {
        let count = 0;
        if (lasso) for (const g of selected) if (level.local[g] >= 0) count++;
        this.selectionCount = count;
        for (let i = 0; i < level.n; i++) this.selTarget[i] = selectionFactor(this.dm.selected[level.ids[i]]);
        this._retargetAlpha(T.SEL_MS);
      }
      this.ui.update();
    }

    _syncColors() {
      const level = this.current();
      if (!level || !level.ids || this._baseColors() === this.colorSource) return;
      this.colorSource = this._baseColors();
      this.rgba = gather(this.colorSource, level.ids, 4);
      this.colorsDirty = true;
    }

    _retargetAlpha(ms) {
      const target = new Float32Array(this.alpha.length);
      for (let i = 0; i < target.length; i++) target[i] = this.visTarget[i] * this.selTarget[i];
      this.alphaTween = { from: this.alpha.slice(), to: target, t0: performance.now(), ms };
    }

    // ---------------------------------------------------------------- lasso
    _lassoFreeze() {
      const lasso = this.dm.lassoSelector;
      if (lasso && lasso.rebuildQuadTree) lasso.rebuildQuadTree(lasso.points, []);
    }

    _lassoLevel(level) {
      const lasso = this.dm.lassoSelector;
      if (!lasso || !lasso.rebuildQuadTree) return;
      const root = this.levels[0];
      if (!level.ids) {
        lasso.rebuildQuadTree(root.pos, null);
        return;
      }
      const all = new Float32Array(2 * root.n).fill(NaN);
      for (let i = 0; i < level.n; i++) {
        all[2 * level.ids[i]] = this.disp[2 * i];
        all[2 * level.ids[i] + 1] = this.disp[2 * i + 1];
      }
      lasso.rebuildQuadTree(all, level.ids);
    }

    _clearLasso() {
      if (this.dm.dataSelectionManager.hasSpecialSelection()) this.dm.removeSelection(this.dm.lassoSelectionItemId);
    }

    // ---------------------------------------------------------------- transitions
    _startTransition(tr) {
      this.tr = { ...tr, t0: performance.now() };
      this.savedController = this.dm.deckgl.props.controller;
      this.dm.deckgl.setProps({ controller: false });
      this._stepTransition(this.tr.t0);
    }

    _stepTransition(now) {
      const tr = this.tr;
      const controller = this.dm.deckgl.props.controller;
      if (controller !== false) {
        // Something (e.g. the lasso's Shift handler) changed the controller mid-transition:
        // keep interaction locked, and restore that newer controller afterwards.
        this.savedController = controller;
        this.dm.deckgl.setProps({ controller: false });
      }
      const t = clamp((now - tr.t0) / tr.dur, 0, 1);
      tr.step(easeInOut(t));
      if (t >= 1) {
        this.tr = null;
        this.dm.deckgl.setProps({ controller: this.savedController });
        tr.onEnd();
      }
    }

    // ---------------------------------------------------------------- re-embed
    canReembed() { return this.mode === "idle" && !this.tr && this.selectionCount >= T.MIN_POINTS; }

    reembed() {
      if (!this.dm.pointLayer || !this.canReembed()) return;
      const dm = this.dm;
      const root = this._root();
      const parent = this.current();
      const selected = dm.getSelectedIndices();
      let parentSel;
      if (!parent.ids) {
        parentSel = Int32Array.from(selected).sort();
      } else {
        const local = [];
        for (let i = 0; i < parent.n; i++) if (selected.has(parent.ids[i])) local.push(i);
        parentSel = Int32Array.from(local);
      }
      const n = parentSel.length;
      if (n < T.MIN_POINTS) return;
      this._stopWorker();
      this.relaxing = false;
      const ids = parent.ids ? gather(parent.ids, parentSel, 1) : parentSel.slice();
      const parentPos = parent.ids ? this.disp.slice() : root.pos;
      const X = gather(parentPos, parentSel, 2);
      const V0 = this._currentView();
      this.view = { ...V0 };
      const k0 = (parent.ids ? this.rs : 1) * 2 ** V0.zoom;
      const minPx0 = parent.ids ? this.minPx : (dm.pointLayer.props.radiusMinPixels ?? dm.pointRadiusMinPixels);
      const opacity0 = parent.ids ? 1 : (dm.pointLayer.props.opacity ?? 1);
      parent.view = V0;
      if (parent.ids) {
        parent.pos = parentPos;
        parent.rs = this.rs;
      } else {
        // Capture before the lasso is cleared: clearing can re-show a suppressed density overview.
        this._captureOthers();
      }

      // Epoch-0 layout: the selection uniformly scaled into the home frame.
      const fitIdx = sampleIndices(n);
      const bx = robustBounds(X, fitIdx);
      const scale = (root.homeExtent * T.HOME_FILL) / Math.max(bx[1] - bx[0], bx[3] - bx[2], 1e-9);
      const homeMap = { scale, xc: (bx[0] + bx[1]) / 2, yc: (bx[2] + bx[3]) / 2, hx: root.homeCenter[0], hy: root.homeCenter[1] };
      const P1 = new Float32Array(2 * n);
      for (let i = 0; i < 2 * n; i += 2) {
        P1[i] = homeMap.hx + (X[i] - homeMap.xc) * scale;
        P1[i + 1] = homeMap.hy + (X[i + 1] - homeMap.yc) * scale;
      }
      const V1 = fitView(robustBounds(P1, fitIdx), this._viewportSize());

      // Point size: grow with sparsity relative to the full map's look at its home view.
      const radii = root.radii ? gather(root.radii, ids, 1) : null;
      const rMed = radii ? medianOf(radii, fitIdx) : root.rMed;
      const rpxHome = Math.max(root.rMed * 2 ** root.homeZoom, dm.pointRadiusMinPixels);
      const rpxTarget = clamp(rpxHome * Math.sqrt(root.n / n), rpxHome, Math.max(T.MAX_PX, rpxHome));
      const k1 = rpxTarget / rMed;

      // The parent's other points become a ghost layer that shrinks and fades out.
      const base = parent.ids ? this.colors : this._baseColors();
      const ghostRgba = new Uint8Array(base);
      if (!parent.ids) {
        for (let i = 0; i < root.n; i++) ghostRgba[4 * i + 3] = Math.round(ghostRgba[4 * i + 3] * selectionFactor(dm.selected[i]));
      }
      for (const i of parentSel) ghostRgba[4 * i + 3] = 0;
      const ghostRadii = parent.ids ? parent.radii : root.radii;
      const local = new Int32Array(root.n).fill(-1);
      for (let t = 0; t < n; t++) local[ids[t]] = t;

      const level = { ids, n, X, homeMap, pos: P1, view: null, parentSel, fitIdx, radii, rMed, local, rs: k1 / 2 ** V1.zoom };
      // The parent's labels (if it is a re-embedding) follow its points out while the new ones fade in.
      const parentLabels = parent.ids && this.labels ? { items: this.labels.items, opacity: this.labels.opacity } : null;
      this.levels.push(level);
      this._showLevel(level, X, 0);
      this.ghostLabels = parentLabels;
      this.rs = k0 / 2 ** V0.zoom;
      this.minPx = minPx0;
      this.opacity = opacity0;
      this.ghost = { n: parent.n, pos: parentPos.slice(), rgba: ghostRgba, radii: ghostRadii, rs: this.rs, minPx: minPx0, opacity: opacity0 };
      this._clearLasso();
      this._lassoFreeze();
      this.mode = "entering";
      this.autofit = false;
      this.map = null;
      Object.assign(this.status, { phase: "zooming", epoch: 0, nEpochs: 0, error: null, engine: null, timing: null, buildMs: 0 });

      const zoomIn = () => {
        // Snap the camera to V1, re-expressing everything so nothing moves on screen.
        const P0 = reexpress(X, V0, V1);
        const selTween = zoomTween(P0, P1);
        const ghostTween = followTween(reexpress(parentPos, V0, V1), selTween);
        this._setView(V1);
        this._setFilter("all");
        this.disp.set(P0);
        tweenAt(ghostTween, 0, this.ghost.pos);
        const baseMin = dm.pointRadiusMinPixels;
        const ghostOpacity = this.ghost.opacity;
        const scaleAt = (k) => k / 2 ** V1.zoom;
        this._startTransition({
          dur: T.ZOOM_MS,
          step: (e) => {
            tweenAt(selTween, e, this.disp);
            this.rs = scaleAt(k0 ** (1 - e) * k1 ** e);
            this.minPx = lerp(minPx0, baseMin, e);
            tweenAt(ghostTween, e, this.ghost.pos);
            this.ghost.rs = scaleAt(k0 * (1 - e) ** 0.8);
            this.ghost.minPx = minPx0 * (1 - e);
            this.ghost.opacity = ghostOpacity * (1 - e);
            if (this.ghostLabels) this.ghostLabels.opacity = 1 - smoothstep(e / 0.5);
            this.labels.opacity = smoothstep((e - 0.35) / 0.65);
          },
          onEnd: () => {
            this.ghost = null;
            this.ghostLabels = null;
            this.labels.opacity = 1;
            this.opacity = 1;
            this.autofit = true;
            this.mode = this.status.error ? "idle" : "running";
            if (this.mode === "idle") this._finishLevel();
            if (this.status.phase === "zooming") this.status.phase = "computing kNN graph";
            if (this.worker) this.worker.postMessage({ cmd: "resume" });
            if (this.map && this.target) this._startFrameTween(performance.now());
          },
        });
      };

      if (parent.ids) {
        zoomIn();
      } else {
        // First level: fade out labels and other layers before the camera moves.
        this._setFilter("points");
        this._startTransition({
          dur: T.PREFADE_MS,
          step: (e) => {
            this._setOthersOpacity(1 - e);
            this.opacity = lerp(opacity0, 1, e);
            this.ghost.opacity = lerp(opacity0, 1, e);
          },
          onEnd: () => {
            this._setOthersOpacity(1);
            zoomIn();
          },
        });
      }
      this.ui.update();
      this._request(level);
    }

    async _request(level) {
      const n = level.n;
      const base = this._serverBase();
      if (!base) {
        this._fail("No re-embed server configured: pass ReembedWidget(server_url=...).");
        return;
      }
      const gpu = this.engine() !== "cpu" && (await gpuAvailable());
      const threshold = this.cfg.subsample_threshold || (gpu ? 400000 : 25000);
      const sample = n > threshold ? Math.min(this.cfg.sample_size, n - 1) : 0;
      const t0 = performance.now();
      // Ask for the selection in spatial order: the graph then encodes compactly.
      const order = n < 16777216 ? spatialOrder(level.X, n) : null;
      let body = level.ids;
      if (order) {
        body = new Int32Array(n);
        for (let r = 0; r < n; r++) body[r] = level.ids[order[r]];
      }
      const tSend = performance.now();
      let header, arrays, buffer, resp, tHeaders, tBody;
      try {
        resp = await fetch(base + "/api/reembed?encoding=varint" + (sample ? "&sample=" + sample : ""), {
          method: "POST",
          body,
          headers: { "Content-Type": "application/octet-stream", ...(this.cfg.auth_headers || {}) },
        });
        if (!resp.ok) throw new Error(`server responded ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
        tHeaders = performance.now();
        buffer = await resp.arrayBuffer();
        tBody = performance.now();
        ({ header, arrays } = unpack(buffer));
      } catch (error) {
        if (this.current() === level && !level.cancelled) this._fail(`Re-embed request failed (${error.message || error}).`);
        return;
      }
      if (this.current() !== level || level.cancelled) return;  // the user went back meanwhile
      let knn = { idx: arrays.knn_indices, dist: arrays.knn_distances };
      let sampleLocal = arrays.sample_local || null;
      if (order) {
        knn = reorderKnn(knn.idx, knn.dist, order);
        if (sampleLocal) sampleLocal = sampleLocal.map((r) => order[r]);
      }
      level.sampleLocal = sampleLocal;
      // Kept so the level can be re-optimized later (e.g. after Back) without a new request.
      level.knn = knn;
      const tDone = performance.now();
      // Where the request time went. Upload and server times are measured by the server;
      // "other" is latency plus preparing and decoding here.
      const net = performance.getEntriesByName(resp.url).pop();
      const timing = {
        totalMs: tDone - t0,
        prepareMs: tSend - t0,
        firstByteMs: tHeaders - tSend,
        uploadMs: header.receiveSeconds != null ? 1000 * header.receiveSeconds : null,
        serverMs: 1000 * (header.serverSeconds ?? header.knnSeconds + (header.sampleKnnSeconds || 0)),
        knnMs: 1000 * (header.knnSeconds + (header.sampleKnnSeconds || 0)),
        downloadMs: tBody - tHeaders,
        networkDownloadMs: net && net.responseEnd > 0 ? net.responseEnd - net.responseStart : null,
        decodeMs: tDone - tBody,
        uploadBytes: body.byteLength,
        downloadBytes: buffer.byteLength,
      };
      timing.otherMs = timing.totalMs - (timing.uploadMs || 0) - timing.serverMs - timing.downloadMs;
      console.info("[reembed] " + n + " points, request timing:", timing);
      this.status.timing = timing;
      this.status.phase = "building";
      this._spawnWorker(level, level.X, level.homeMap, {
        startPaused: !!this.tr,
        sample: sampleLocal
          ? { local: sampleLocal, idx: arrays.sample_knn_indices, dist: arrays.sample_knn_distances }
          : null,
      });
    }

    /**
     * Start a worker optimizing `level` from positions `X` (display coordinates of
     * the epoch-0 layout before `homeMap`).
     */
    _spawnWorker(level, X, homeMap, { startPaused = false, sample = null } = {}) {
      const assets = this._engineAssets();
      this._stopWorker();
      this.runId++;
      this.runInit = { X, homeMap };
      this.worker = new Worker(assets.url);
      this.worker.onmessage = (e) => this._onWorkerMessage(e.data, level);
      this.worker.onerror = (e) => {
        if (this.current() === level && !level.cancelled) this._fail(`Engine error: ${e.message || e}`);
      };
      this.worker.postMessage({
        cmd: "start", engine: this.engine(), wasmGz: assets.wasmGz, startPaused, runId: this.runId,
        n: level.n, initXY: X, knnIdx: level.knn.idx, knnDist: level.knn.dist, sample,
        options: { ...this.ui.params(), refineEpochs: this.cfg.refine_epochs, initRescale: this.cfg.init_rescale },
      });
    }

    engine() { return this.ui.engine() || this.cfg.engine || "auto"; }

    _engineAssets() {
      if (!this.assets) {
        const src = document.getElementById(this.cfg.engine_source_id).textContent;
        const b64 = document.getElementById(this.cfg.engine_wasm_id).textContent.trim();
        const bin = atob(b64);
        const wasmGz = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) wasmGz[i] = bin.charCodeAt(i);
        this.assets = { url: URL.createObjectURL(new Blob([src], { type: "text/javascript" })), wasmGz };
      }
      return this.assets;
    }

    _fail(message) {
      this.status.error = message;
      this.status.phase = "error";
      this._stopWorker();
      if (!this.tr && this.mode !== "back") {
        this.mode = "idle";
        this._finishLevel();
      }
      this.ui.update();
    }

    _stopWorker() {
      if (this.worker) {
        this.worker.postMessage({ cmd: "stop" });
        this.worker.terminate();
        this.worker = null;
      }
    }

    /** Optimizer coords -> display: undo the epoch-0 similarity, then apply the home map. */
    _displayMap(Y0, idx) {
      const { X, homeMap } = this.runInit;
      const Xs = idx ? gather(X, idx, 2) : X;
      const f = fitSimilarity(Xs, Y0);
      const { scale, xc, yc, hx, hy } = homeMap;
      return (Y, out, ix = null) => {
        const k = ix ? ix.length : Y.length / 2;
        for (let t = 0; t < k; t++) {
          const i = ix ? ix[t] : t;
          out[2 * i] = hx + ((Y[2 * t] - f.tx) / f.s - xc) * scale;
          out[2 * i + 1] = hy + ((Y[2 * t + 1] - f.ty) / f.s - yc) * scale;
        }
      };
    }

    _startFrameTween(now) {
      this.ft = { from: this.disp.slice(), to: this.target.slice(), t0: now, dur: clamp(this.interArrival, 16, 600) };
    }

    _onWorkerMessage(msg, level) {
      if (this.current() !== level || level.cancelled) return;
      // Messages from a run superseded by a parameter change.
      if (msg.runId !== undefined && msg.runId !== this.runId) return;
      const now = performance.now();
      const st = this.status;
      if (msg.type === "error") {
        console.error(msg.error);
        this._fail(`Engine error: ${msg.error.split("\n")[0]}`);
        return;
      }
      if (msg.type === "engine") {
        st.engine = msg;
        if (msg.buildMs != null) st.buildMs = msg.buildMs;
        this.ui.update();
        return;
      }
      if (msg.type === "sample") return;
      if (msg.type === "placed") {
        this.map(msg.embedding, this.target);
        // Points hidden during the sample phase jump to their placed positions, then fade in.
        for (let i = 0; i < level.n; i++) {
          if (this.alpha[i] < 0.01) {
            this.disp[2 * i] = this.target[2 * i];
            this.disp[2 * i + 1] = this.target[2 * i + 1];
          }
        }
        this.visTarget.fill(1);
        this._retargetAlpha(T.FADE_MS);
        this.sampleLocal = null;
        st.phase = "building full layout";
        if (!this.tr) this._startFrameTween(now);
        return;
      }
      if (msg.type === "done") {
        // The worker stays alive (idle) so parameter changes can re-optimize quickly.
        st.phase = "done";
        return;
      }
      if (msg.type !== "frame") return;
      if (msg.restarted) this.relaxing = true;
      st.phase = this.relaxing || msg.phase === "relax" ? "re-optimizing"
        : msg.phase === "full" ? "optimizing" : msg.phase === "sample" ? "optimizing sample" : "refining";
      st.epoch = msg.epoch;
      st.nEpochs = msg.nEpochs;
      if (msg.computeMs) st.computeMs = msg.computeMs;
      const idx = msg.phase === "sample" ? this.sampleLocal : null;
      if (msg.initial) {
        if (msg.phase === "sample") {
          // Hide non-sample points until they are placed.
          this.sampleLocal = level.sampleLocal;
          this.visTarget.fill(0);
          for (const i of this.sampleLocal) this.visTarget[i] = 1;
          this._retargetAlpha(T.FADE_MS);
        }
        const sidx = msg.phase === "sample" ? this.sampleLocal : null;
        this.map = this._displayMap(msg.embedding, sidx);
        this.target = (this.tr ? level.pos : this.disp).slice();
        this.map(msg.embedding, this.target, sidx);
        this.lastArrival = now;
        return;
      }
      this.interArrival = 0.8 * this.interArrival + 0.2 * Math.min(1000, now - this.lastArrival);
      this.lastArrival = now;
      this.map(msg.embedding, this.target, idx);
      if (!this.tr) this._startFrameTween(now);
    }

    _finishLevel() {
      const level = this.current();
      level.pos = this.disp.slice();
      level.rs = this.rs;
      this.autofit = false;
      this._lassoLevel(level);
      this._render();
    }

    _finishRun() {
      this.mode = "idle";
      this.relaxing = false;
      this._finishLevel();
      this.ui.update();
    }

    pause(paused) {
      if (this.worker) this.worker.postMessage({ cmd: paused ? "pause" : "resume" });
    }

    /**
     * New min_dist / spread / repulsion: restart the optimization of the shown
     * re-embedding from its current layout (during or after a run).
     */
    setParams(params) {
      const level = this.current();
      if (!level || !level.ids || level.cancelled || this.mode === "back") return;
      if (this.worker) {
        this.runId++;
        this.worker.postMessage({ cmd: "params", params, runId: this.runId });
      } else if (this.mode === "idle" && level.knn && this.disp) {
        this._spawnWorker(level, this.disp.slice(), IDENTITY_MAP);
      } else {
        return;  // the run that is about to start reads the new values
      }
      if (this.mode !== "idle") return;
      // Continue from the current look: keep point size and resume auto-fit unless the user moved the camera.
      this.status.phase = "re-optimizing";
      this.status.error = null;
      this.relaxing = true;
      level.rs = this.rs;
      level.fitZoom = this.view.zoom;
      this.autofit = !level.userCamera;
      this.ft = null;
      this.mode = "running";
      this._lassoFreeze();
      this.ui.update();
    }

    // ---------------------------------------------------------------- back
    back(toDepth = this.depth - 1) {
      if (this.depth < 1 || this.tr || toDepth < 0 || toDepth >= this.depth) return;
      // Levels being left must ignore any kNN response or worker message still in flight.
      for (let d = toDepth + 1; d <= this.depth; d++) this.levels[d].cancelled = true;
      this._stopWorker();
      this.relaxing = false;
      this.ft = null;
      // Collapse intermediate levels so the current points map straight to the target ancestor.
      while (this.depth > toDepth + 1) {
        const child = this.levels.pop();
        const mid = this.current();
        Object.assign(mid, {
          parentSel: child.parentSel.map((i) => mid.parentSel[i]),
          ids: child.ids, n: child.n, radii: child.radii, fitIdx: child.fitIdx, local: child.local, rMed: child.rMed,
          labels: child.labels, knn: child.knn,
        });
      }
      const dm = this.dm;
      const root = this.levels[0];
      const child = this.current();
      const parent = this.levels[this.depth - 1];
      const Vc = { ...(this.view || this._currentView()) };
      const Vp = parent.view;
      const kc = this.rs * 2 ** Vc.zoom;
      const kp = (parent.ids ? parent.rs : 1) * 2 ** Vp.zoom;
      const parentPos = parent.ids ? parent.pos : root.pos;
      const childTarget = reexpress(gather(parentPos, child.parentSel, 2), Vp, Vc);
      const selTween = zoomTween(this.disp.slice(), childTarget);
      const ghostEnd = reexpress(parentPos, Vp, Vc);
      const ghostStart = new Float32Array(ghostEnd.length);
      for (let i = 0; i < ghostEnd.length; i += 2) {
        ghostStart[i] = selTween.cx + (ghostEnd[i] - selTween.cx) / selTween.k;
        ghostStart[i + 1] = selTween.cy + (ghostEnd[i + 1] - selTween.cy) / selTween.k;
      }
      const ghostRgba = new Uint8Array(parent.ids ? gather(this._baseColors(), parent.ids, 4) : this._baseColors());
      for (const i of child.parentSel) ghostRgba[4 * i + 3] = 0;
      const ghostTween = followTween(ghostStart, selTween);
      this._clearLasso();
      this._lassoFreeze();
      let minPxEnd = dm.pointRadiusMinPixels;
      let opacityEnd = 1;
      if (!parent.ids) {
        // Bring DataMap's view-dependent state (density crossfade, hex bins, minimap) to the
        // parent view now, so the animation ends exactly on the point layer's look there.
        dm._densityOverviewLastT = null;
        dm.notifyViewStateChange({ ...Vp });
        minPxEnd = dm.pointLayer.props.radiusMinPixels ?? minPxEnd;
        opacityEnd = dm.pointLayer.props.opacity ?? 1;
      }
      const minPx0 = this.minPx;
      this.ghost = { n: parent.n, pos: ghostStart.slice(), rgba: ghostRgba, radii: parent.ids ? parent.radii : root.radii, rs: 0, minPx: 0, opacity: 0 };
      // The shown labels fade out; a re-embedded parent's labels fade in on its returning points.
      this.ghostLabels = parent.ids ? { items: this._levelLabels(parent), opacity: 0 } : null;
      const labelOpacity0 = this.labels ? this.labels.opacity : 0;
      this.visTarget.fill(1);
      this.selTarget.fill(1);
      this._retargetAlpha(T.BACK_MS);
      this.mode = "back";
      this.autofit = false;
      this.status.phase = "back";
      const scaleAt = (k) => k / 2 ** Vc.zoom;
      this._startTransition({
        dur: T.BACK_MS,
        step: (e) => {
          tweenAt(selTween, e, this.disp);
          this.rs = scaleAt(kc ** (1 - e) * kp ** e);
          this.minPx = lerp(minPx0, minPxEnd, e);
          this.opacity = lerp(1, opacityEnd, e);
          tweenAt(ghostTween, e, this.ghost.pos);
          this.ghost.rs = scaleAt(kp * e ** 0.8);
          this.ghost.minPx = minPxEnd * e;
          this.ghost.opacity = opacityEnd * e;
          if (this.labels) this.labels.opacity = labelOpacity0 * (1 - smoothstep(e / 0.5));
          if (this.ghostLabels) this.ghostLabels.opacity = smoothstep((e - 0.35) / 0.65);
        },
        onEnd: () => {
          this.ghost = null;
          this.ghostLabels = null;
          this._setView(Vp);
          this.levels.pop();
          if (parent.ids) {
            this._showLevel(parent, parent.pos);
            this.rs = parent.rs;
            this.minPx = minPxEnd;
            this.opacity = 1;
            this.mode = "idle";
            Object.assign(this.status, { phase: "", error: null });
            this._finishLevel();
          } else {
            this._exitToRoot();
          }
          this.ui.update();
        },
      });
      this.ui.update();
    }

    _exitToRoot() {
      const dm = this.dm;
      this.disp = null;
      this.labels = null;
      this.mode = "idle";
      Object.assign(this.status, { phase: "", error: null, epoch: 0, nEpochs: 0 });
      dm.layers = dm.layers.filter((layer) => !isOurs(layer));
      this._captureOthers();
      this._setOthersOpacity(0);
      this._setFilter("none");
      dm.deckgl.setProps({ layers: dm.layers });
      this._lassoLevel(this.levels[0]);
      this._startTransition({
        dur: T.FADEIN_MS,
        step: (e) => {
          this._setOthersOpacity(e);
          dm.deckgl.setProps({ layers: dm.layers });
        },
        onEnd: () => {
          this._setOthersOpacity(1);
          dm.deckgl.setProps({ layers: dm.layers });
        },
      });
    }

    // ---------------------------------------------------------------- frame loop
    _autofitStep(dt) {
      const level = this.current();
      const b = robustBounds(this.disp, level.fitIdx, this.alpha);
      if (!b) return;
      const target = fitView(b, this._viewportSize());
      if (![target.longitude, target.latitude, target.zoom].every(Number.isFinite)) return;
      const cur = this.view;
      const dz = target.zoom - cur.zoom;
      const ppr = pxPerRad(cur.zoom);
      const dxPx = (target.longitude - cur.longitude) * D2R * ppr;
      const dyPx = (mercY(target.latitude) - mercY(cur.latitude)) * ppr;
      if (Math.abs(dz) < 0.02 && Math.hypot(dxPx, dyPx) < 2) return;  // dead band
      const k = 1 - Math.exp(-dt / (dz < 0 ? T.TAU_OUT : T.TAU_IN));
      this._setView({
        longitude: cur.longitude + (target.longitude - cur.longitude) * k,
        latitude: invMercY(mercY(cur.latitude) + (mercY(target.latitude) - mercY(cur.latitude)) * k),
        zoom: cur.zoom + dz * k,
      });
    }

    _tick() {
      requestAnimationFrame(() => this._tick());
      // Not the rAF timestamp: it can precede the arrival times of worker frames in this frame.
      const now = performance.now();
      const dt = clamp((now - this.lastTick) / 1000, 0, 0.1);
      this.lastTick = now;
      if (!this.dm.pointLayer) return;
      this._syncSelection();
      this._syncColors();
      const level = this.current();
      let dirty = false;
      if (this.tr) {
        this._stepTransition(now);
        dirty = true;
      } else if (this.ft) {
        const t = clamp((now - this.ft.t0) / this.ft.dur, 0, 1);
        for (let i = 0; i < this.disp.length; i++) this.disp[i] = lerp(this.ft.from[i], this.ft.to[i], t);
        if (t >= 1) {
          this.ft = null;
          if (this.status.phase === "done" && this.mode === "running") this._finishRun();
        }
        dirty = true;
      } else if (this.status.phase === "done" && this.mode === "running") {
        this._finishRun();
      }
      if (this.alphaTween && this.disp) {
        const a = this.alphaTween, t = clamp((now - a.t0) / a.ms, 0, 1), e = easeInOut(t);
        for (let i = 0; i < this.alpha.length; i++) this.alpha[i] = lerp(a.from[i], a.to[i], e);
        if (t >= 1) this.alphaTween = null;
        this.colorsDirty = true;
        dirty = true;
      }
      if (this.colorsDirty && this.disp) dirty = true;
      if (!this.tr && this.mode === "running" && this.autofit && this.disp) {
        // The camera follows the layout; points keep their on-screen size meanwhile.
        const k = level.rs * 2 ** (level.fitZoom ?? this.view.zoom);
        this._autofitStep(dt);
        this.rs = k / 2 ** this.view.zoom;
        level.rs = this.rs;
        level.fitZoom = this.view.zoom;
        dirty = true;
      }
      if (dirty && this.disp && this.depth > 0) this._render();
      if (now - (this.lastUi || 0) > 100) {
        this.lastUi = now;
        this.ui.update();
      }
    }
  }

  // ---------------------------------------------------------------- UI
  class Widget {
    constructor(containerId, config, datamap) {
      this.container = document.getElementById(containerId);
      this.cfg = config;
      this.dm = datamap;
      this._render();
      this.controller = new ReembedController(datamap, config, this);
      this.update();
    }

    _render() {
      const c = this.cfg;
      this.container.innerHTML = `
        <div class="reembed-widget">
          <div class="reembed-title"></div>
          <div class="reembed-buttons">
            <button class="reembed-go" disabled>Re-embed</button>
            <button class="reembed-pause" disabled>Pause</button>
            <button class="reembed-back" disabled>Back</button>
          </div>
          <div class="reembed-crumbs"></div>
          <div class="reembed-progress"><div class="reembed-progress-bar"></div></div>
          <div class="reembed-status"></div>
          <details class="reembed-settings">
            <summary>Settings</summary>
            <div class="reembed-row"><span class="reembed-row-label">Engine</span>
              <div class="reembed-options reembed-engine">
                <button data-value="auto" title="WebGPU when available, else CPU">Auto</button>
                <button data-value="gpu">WebGPU</button>
                <button data-value="cpu">CPU</button>
              </div></div>
            <div class="reembed-row"><span class="reembed-row-label">Epochs</span>
              <input class="reembed-epochs" type="number" min="10" max="2000" step="10" value="${c.n_epochs}"></div>
            <div class="reembed-row"><span class="reembed-row-label">min_dist</span>
              <input class="reembed-slider reembed-min-dist" type="range" min="0" max="0.99" step="0.01" value="${c.min_dist}">
              <span class="reembed-row-value"></span></div>
            <div class="reembed-row"><span class="reembed-row-label">spread</span>
              <input class="reembed-slider reembed-spread" type="range" min="0.5" max="3" step="0.05" value="${c.spread}">
              <span class="reembed-row-value"></span></div>
            <div class="reembed-row"><span class="reembed-row-label">repulsion</span>
              <input class="reembed-slider reembed-repulsion" type="range" min="0.1" max="3" step="0.05" value="${c.repulsion_strength}">
              <span class="reembed-row-value"></span></div>
          </details>
          <div class="reembed-hint">Hold Shift and drag to lasso points, then Re-embed.
            Changing min_dist, spread or repulsion re-optimizes the current layout.</div>
        </div>`;
      const q = (s) => this.container.querySelector(s);
      if (c.title) q(".reembed-title").textContent = c.title;
      else q(".reembed-title").remove();
      this.el = {
        go: q(".reembed-go"), pause: q(".reembed-pause"), back: q(".reembed-back"), crumbs: q(".reembed-crumbs"),
        bar: q(".reembed-progress-bar"), status: q(".reembed-status"), engine: q(".reembed-engine"),
        epochs: q(".reembed-epochs"), minDist: q(".reembed-min-dist"), spread: q(".reembed-spread"), repulsion: q(".reembed-repulsion"),
      };
      this.engineValue = c.engine || "auto";
      const engineButtons = Array.from(this.el.engine.querySelectorAll("button"));
      const showEngine = () => engineButtons.forEach((b) => b.classList.toggle("reembed-active-option", b.dataset.value === this.engineValue));
      engineButtons.forEach((b) => {
        b.onclick = () => { this.engineValue = b.dataset.value; showEngine(); };
      });
      showEngine();
      this.el.go.onclick = () => this.controller.reembed();
      this.el.back.onclick = () => this.controller.back();
      this.el.pause.onclick = () => {
        this.paused = !this.paused;
        this.controller.pause(this.paused);
        this.update();
      };
      for (const key of ["minDist", "spread", "repulsion"]) {
        const input = this.el[key];
        const show = () => { input.nextElementSibling.textContent = Number(input.value).toFixed(2); };
        show();
        input.oninput = () => {
          show();
          const { nEpochs, ...live } = this.params();
          this.controller.setParams(live);
        };
      }
    }

    params() {
      return {
        nEpochs: Math.max(10, Number(this.el.epochs.value) || this.cfg.n_epochs),
        minDist: Number(this.el.minDist.value),
        spread: Number(this.el.spread.value),
        repulsionStrength: Number(this.el.repulsion.value),
      };
    }

    engine() { return this.engineValue; }

    update() {
      const ctl = this.controller;
      if (!ctl) return;
      const st = ctl.status;
      const n = ctl.selectionCount;
      this.el.go.disabled = !ctl.canReembed();
      this.el.go.textContent = n ? `Re-embed ${n.toLocaleString()}` : "Re-embed";
      this.el.back.disabled = ctl.depth < 1 || !!ctl.tr;
      const running = ctl.mode === "running" && !!ctl.worker;
      if (!running) this.paused = false;
      this.el.pause.disabled = !running;
      this.el.pause.textContent = this.paused ? "Resume" : "Pause";
      const crumbs = this.el.crumbs;
      const crumbKey = ctl.depth > 0 ? ctl.levels.map((level) => level.n).join("/") + (ctl.tr ? "*" : "") : "";
      if (crumbKey !== this.crumbKey) {
        this.crumbKey = crumbKey;
        crumbs.innerHTML = "";
        if (ctl.depth > 0) {
          ctl.levels.forEach((level, d) => {
            const link = d < ctl.depth && !ctl.tr;
            const el = document.createElement(link ? "a" : "b");
            el.textContent = d === 0 ? "Full map" : level.n.toLocaleString();
            if (link) {
              el.href = "#";
              el.onclick = (e) => { e.preventDefault(); ctl.back(d); };
            }
            if (d) crumbs.append(" › ");
            crumbs.append(el);
          });
        }
      }
      const frac = st.nEpochs ? st.epoch / st.nEpochs : 0;
      this.el.bar.parentElement.style.visibility = ctl.depth > 0 || ctl.mode !== "idle" ? "visible" : "hidden";
      this.el.bar.style.width = `${(100 * (ctl.mode === "running" || st.phase === "done" ? frac : 0)).toFixed(1)}%`;
      let text = "";
      const serverText = ctl.serverText();
      if (st.error) {
        text = st.error;
      } else if (ctl.depth > 0 || ctl.mode !== "idle") {
        const e = st.engine;
        const engine = e ? (e.gpuActive ? "WebGPU" : "CPU") + (e.gpuRequested && !e.gpuActive ? " (GPU unavailable)" : "") : "";
        const parts = [];
        if (st.phase === "computing kNN graph" && serverText) parts.push("waiting for server: " + ctl.server.stage);
        else if (st.phase && st.phase !== "done") parts.push(st.phase);
        if (st.nEpochs) parts.push(`epoch ${st.epoch}/${st.nEpochs}`);
        if (engine) parts.push(engine + (st.computeMs ? ", " + st.computeMs.toFixed(1) + " ms/epoch" : ""));
        // Where the time went: the request (upload, server, download), and building the optimizer.
        const tm = st.timing;
        if (tm) {
          const sec = (ms) => (ms / 1000).toFixed(2) + " s";
          const mb = (b) => (b / 1e6).toFixed(b < 1e6 ? 2 : 1) + " MB";
          parts.push("request " + sec(tm.totalMs) + " ("
            + (tm.uploadMs != null ? "upload " + mb(tm.uploadBytes) + " " + sec(tm.uploadMs) + ", " : "")
            + "server " + sec(tm.serverMs) + " incl. kNN " + sec(tm.knnMs)
            + ", download " + mb(tm.downloadBytes) + " " + sec(tm.downloadMs)
            + ", other " + sec(tm.otherMs) + ")");
        }
        if (st.buildMs) parts.push("setup " + (st.buildMs / 1000).toFixed(2) + " s");
        text = parts.join(" · ");
      } else {
        text = serverText;
      }
      this.el.status.textContent = text;
      this.el.status.title = st.timing && !st.error
        ? Object.entries(st.timing).map(([k, v]) => k + ": " + (v == null ? "-" : Math.round(v))).join("\n") : "";
      this.el.status.classList.toggle("reembed-error", !!st.error);
    }
  }

  return Widget;
})();
