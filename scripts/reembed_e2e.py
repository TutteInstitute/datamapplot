"""End-to-end browser check of the ReembedWidget (developer script).

Builds a 20 Newsgroups data map with a ReembedWidget, serves it from a
ReembedServer and drives headless Chromium through lasso -> re-embed ->
nested re-embed -> back -> back, checking for console errors and that the
original map is restored exactly.

    python scripts/reembed_e2e.py [--data ng20.parquet] [--browser firefox] [--headed]
        [--engine cpu] [--subsample] [--slow-link KB_PER_S] [--density] [--shots DIR] [--no-minify]

Requires pynndescent and playwright (``playwright install chromium``).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import datamapplot
from datamapplot.reembed_server import ReembedServer

DATA_URL = (
    "https://huggingface.co/datasets/lmcinnes/20newsgroups_topics/"
    "resolve/main/newsgroups_with_topics_customised.parquet"
)

# Page-side helpers: lasso a disc around a data point, read controller state.
HELPERS = """
window.__reembed = {
  ctl: () => window.datamap.widgets.reembed.controller,
  lassoNear: (frac) => {
    const dm = window.datamap, ctl = window.__reembed.ctl();
    const level = ctl.current();
    const pos = level && level.ids ? ctl.disp : dm.pointLayer.props.data.attributes.getPosition.value;
    const n = pos.length / 2;
    const c = Math.floor(n * 0.37) % n;
    const cx = pos[2 * c], cy = pos[2 * c + 1];
    const d = [];
    for (let i = 0; i < n; i++) d.push([(pos[2 * i] - cx) ** 2 + (pos[2 * i + 1] - cy) ** 2, i]);
    d.sort((a, b) => a[0] - b[0]);
    const r = Math.sqrt(d[Math.floor(n * frac)][0]);
    const poly = [];
    for (let k = 0; k < 48; k++) {
      const a = (2 * Math.PI * k) / 48;
      poly.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
    }
    dm.lassoSelector.onLassoComplete(poly);
    return ctl.selectionCount;
  },
  // Screen positions (px) and radius of tracked global ids, measured every frame and
  // immediately before/after each camera snap (which must be invisible).
  record: (ids) => {
    const rec = (window.__reembed.rec = { frames: [], snaps: [] });
    const dm = window.datamap, ctl = window.__reembed.ctl();
    const find = (arr, g) => { let lo = 0, hi = arr.length - 1; while (lo <= hi) { const m = (lo + hi) >> 1; if (arr[m] === g) return m; if (arr[m] < g) lo = m + 1; else hi = m - 1; } return -1; };
    const measure = (track = ids) => {
      const root = dm.pointLayer.props.data.attributes;
      const vp = dm.deckgl.viewManager.getViewports()[0];
      const level = ctl.current();
      const sub = !!(ctl.disp && level && level.ids);
      const pts = track.map((g) => {
        if (!sub) return vp.project([root.getPosition.value[2 * g], root.getPosition.value[2 * g + 1]]);
        const i = find(level.ids, g);
        return i < 0 ? null : vp.project([ctl.disp[2 * i], ctl.disp[2 * i + 1]]);
      });
      const rpx = sub
        ? Math.max(ctl.rs * 2 ** vp.zoom * (level.radii ? level.radii[0] : dm.pointSize), ctl.minPx)
        : Math.max(2 ** vp.zoom * (root.getRadius ? root.getRadius.value[ids[0]] : dm.pointSize), dm.pointLayer.props.radiusMinPixels);
      return { t: performance.now(), mode: ctl.mode, depth: ctl.depth, pts, rpx };
    };
    const setView = ctl._setView.bind(ctl);
    ctl._setView = (v) => {
      if (ctl.mode === "running" && ctl.autofit) return setView(v);
      // Track a sample of the points shown before the snap.
      const level = ctl.current();
      const shown = ctl.disp && level.ids ? level.ids : null;
      const n = shown ? shown.length : dm.pointLayer.props.data.length;
      const track = Array.from({ length: Math.min(n, 400) }, (_, j) => {
        const i = Math.floor(((j + 0.5) * n) / Math.min(n, 400));
        return shown ? shown[i] : i;
      });
      const pre = measure(track);
      setView(v);
      queueMicrotask(() => rec.snaps.push({ pre, post: measure(track) }));
    };
    const step = () => {
      if (window.__reembed.rec !== rec) return;
      requestAnimationFrame(step);
      rec.frames.push(measure());
    };
    requestAnimationFrame(step);
  },
  stopRecording: () => { const rec = window.__reembed.rec; window.__reembed.rec = null; return rec; },
  state: () => {
    const ctl = window.__reembed.ctl(), dm = window.datamap;
    return {
      mode: ctl.mode, depth: ctl.depth, phase: ctl.status.phase, error: ctl.status.error,
      epoch: ctl.status.epoch, nEpochs: ctl.status.nEpochs, engine: ctl.status.engine,
      transition: !!ctl.tr, layers: dm.deckgl.props.layers.map((l) => [l.id, l.props.opacity]),
      filter: !!dm.deckgl.props.layerFilter, view: ctl._currentView(),
      selection: ctl.selectionCount, statusText: document.querySelector('.reembed-status').textContent,
    };
  },
};
"""


def _jump(a, b):
    import math

    both = [math.dist(p, q) for p, q in zip(a["pts"], b["pts"]) if p is not None and q is not None]
    return max(both) if both else None


def analyse_motion(rec):
    """Screen jump (px) and radius change across each camera snap, plus frame stats."""
    snaps = []
    for snap in rec["snaps"]:
        pre, post = snap["pre"], snap["post"]
        snaps.append({
            "from": f"{pre['mode']}@{pre['depth']}", "to": f"{post['mode']}@{post['depth']}",
            "jumpPx": None if _jump(pre, post) is None else round(_jump(pre, post), 3),
            "radiusChangePx": round(abs(post["rpx"] - pre["rpx"]), 4),
        })
    frames = rec["frames"]
    jumps = [j for j in (_jump(a, b) for a, b in zip(frames, frames[1:])) if j is not None]
    return {"frames": len(frames), "maxFrameJumpPx": round(max(jumps), 1) if jumps else None, "snaps": snaps}


def start_throttled_proxy(target_port, down_bytes_per_s, latency_s=0.03):
    """A TCP proxy to 127.0.0.1:target_port limiting each connection's download rate."""
    import asyncio
    import threading

    ready, holder = threading.Event(), {}

    async def pipe(reader, writer, rate):
        try:
            while data := await reader.read(8192):
                await asyncio.sleep(len(data) / rate)
                writer.write(data)
                await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    async def handle(client_reader, client_writer):
        await asyncio.sleep(latency_s)
        server_reader, server_writer = await asyncio.open_connection("127.0.0.1", target_port)
        await asyncio.gather(pipe(client_reader, server_writer, 4 * down_bytes_per_s),
                             pipe(server_reader, client_writer, down_bytes_per_s), return_exceptions=True)

    async def main():
        proxy = await asyncio.start_server(handle, "127.0.0.1", 0)
        holder["port"] = proxy.sockets[0].getsockname()[1]
        ready.set()
        async with proxy:
            await proxy.serve_forever()

    threading.Thread(target=lambda: asyncio.run(main()), daemon=True).start()
    ready.wait()
    return holder["port"]


# Records the controller's worker messages (time, role, type, phase, initial, epoch, nEpochs).
RECORD_MESSAGES = """() => {
  const ctl = window.__reembed.ctl(), handle = ctl._onWorkerMessage.bind(ctl);
  window.__msgs = [];
  ctl._onWorkerMessage = (msg, level, role, worker) => {
    window.__msgs.push([performance.now(), role, msg.type, msg.phase || null, !!msg.initial, msg.epoch ?? null, msg.nEpochs ?? null]);
    return handle(msg, level, role, worker);
  };
}"""


def load_data(path):
    df = pd.read_parquet(path or DATA_URL)
    vectors = np.stack(df["embedding"].values).astype(np.float32)
    layers = [df[f"layer_{i}_topics"].values for i in range(5)]
    return vectors, np.stack(df["map"].values), layers, df["post"].str.slice(0, 120).values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=None, help="local copy of the 20 Newsgroups topics parquet")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "firefox"])
    parser.add_argument("--engine", default="cpu", choices=["auto", "gpu", "cpu"])
    parser.add_argument("--shots", default=None, help="directory for screenshots")
    parser.add_argument("--no-minify", action="store_true")
    parser.add_argument("--subsample", action="store_true",
                        help="force the sample -> place -> refine path for large selections")
    parser.add_argument("--slow-link", type=float, default=None, metavar="KB_PER_S",
                        help="send API requests through a proxy throttled to this download rate, "
                             "so the first level starts from a sample while its full graph downloads")
    parser.add_argument("--density", action="store_true",
                        help="plot with a density overview (shown when zoomed out, suppressed by selections)")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    vectors, data_map, labels, hover = load_data(args.data)
    server = ReembedServer(vectors, metric="cosine", verbose=False).start(port=0)
    widget_args = {"subsample_threshold": 2000, "sample_size": 1500, "refine_epochs": 60} if args.subsample else {}
    if args.slow_link:
        proxy_port = start_throttled_proxy(int(server.url.rsplit(":", 1)[1]), 1000 * args.slow_link)
        widget_args = {"server_url": f"http://127.0.0.1:{proxy_port}", "refine_epochs": 60}
    plot = datamapplot.create_interactive_plot(
        data_map, *labels, hover_text=hover, minify_deps=not args.no_minify, enable_density_overview=args.density,
        widgets=[datamapplot.TitleWidget(title="20 Newsgroups"), datamapplot.ReembedWidget(engine=args.engine, **widget_args)],
    )
    server.serve_figure(plot)
    while not server.global_graph_ready:
        time.sleep(0.2)

    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    errors = []
    failures = []

    def check(cond, message):
        print(("  ok   " if cond else "  FAIL ") + message)
        if not cond:
            failures.append(message)

    with sync_playwright() as p:
        if args.browser == "chromium":
            browser = p.chromium.launch(headless=not args.headed, args=["--enable-unsafe-webgpu"])
        else:
            browser = p.firefox.launch(headless=not args.headed, firefox_user_prefs={"webgl.force-enabled": True, "webgl.disabled": False})
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(server.url)
        page.wait_for_function("window.datamap && window.datamap.widgets && window.datamap.widgets.reembed && window.datamap.lassoSelector", timeout=60000)
        page.evaluate(HELPERS)
        page.wait_for_timeout(500)
        if args.slow_link:
            # As if a previous request had measured the link.
            page.evaluate(f"window.__reembed.ctl().link.downBytesPerMs = {args.slow_link}")
        if args.slow_link or args.subsample:
            page.evaluate(RECORD_MESSAGES)
        state = lambda: page.evaluate("window.__reembed.state()")
        if args.density:
            # The crossfade of points and density overview is only computed on the first
            # view change; compute it now so the map's initial look is the one to restore.
            page.evaluate("window.datamap.notifyViewStateChange(window.datamap.getViewState(), { force: true })")
            page.wait_for_timeout(300)
        s0 = state()
        if shots:
            page.screenshot(path=str(shots / "0_root.png"))

        def run_level(frac, label):
            page.evaluate(f"window.__reembed.lassoNear({frac})")
            page.wait_for_timeout(150)
            count = state()["selection"]
            print(f"{label}: lasso selected {count} points")
            check(count > 50, f"{label}: lasso selection made")
            if label == "level1":
                # Largest opacity at which deck.gl draws any density overview tile, every frame.
                page.evaluate("""() => {
                    const dg = window.datamap.deckgl;
                    const drawn = () => Math.max(0, ...dg.props.layers
                        .filter((l) => l.id.startsWith("densityOverviewLayer") && (!dg.props.layerFilter || dg.props.layerFilter({ layer: l })))
                        .map((l) => l.props.opacity ?? 1));
                    window.__density = { before: drawn(), max: 0 };
                    const step = () => {
                        if (!window.__density.sampling) return;
                        window.__density.max = Math.max(window.__density.max, drawn());
                        requestAnimationFrame(step);
                    };
                    window.__density.sampling = true;
                    requestAnimationFrame(step);
                }""")
            t0 = time.time()
            if label != "level1":
                page.click(".reembed-go")
            else:
                # Shift (lasso mode) during a transition must not unlock interaction; its
                # setting applies once the transition ends, keeping smooth scroll zoom.
                locked = page.evaluate("""() => {
                    document.querySelector(".reembed-go").click();
                    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Shift" }));
                    return !!window.__reembed.ctl().tr && window.datamap.deckgl.props.controller === false;
                }""")
                page.wait_for_function("!window.__reembed.ctl().tr", timeout=60000)
                after = page.evaluate("window.datamap.deckgl.props.controller")
                page.evaluate("document.dispatchEvent(new KeyboardEvent('keyup', { key: 'Shift' }))")
                released = page.evaluate("window.datamap.deckgl.props.controller")
                check(locked and after and after["dragPan"] is False and released["dragPan"] is True
                      and released["scrollZoom"]["smooth"] is True,
                      f"{label}: interaction locked during the transition, lasso mode applied after it")
            page.wait_for_function("window.__reembed.state().mode !== 'idle'", timeout=5000)
            page.wait_for_timeout(600)
            if shots:
                page.screenshot(path=str(shots / f"{label}_zoom.png"))
            try:
                page.wait_for_function("window.__reembed.state().phase === 'done' || !!window.__reembed.state().error", timeout=120000)
                page.wait_for_function("window.__reembed.state().mode === 'idle'", timeout=10000)
            except Exception:
                print(json.dumps({k: v for k, v in state().items() if k != "layers"}))
                print(errors[:5])
                raise
            s = state()
            print(f"{label}: done in {time.time() - t0:.1f}s; status: {s['statusText']}")
            if label == "level1":
                density = page.evaluate("(() => { window.__density.sampling = false; return window.__density; })()")
                check(density["max"] <= density["before"] + 1e-6,
                      f"{label}: density overview not shown while entering ({density['before']} -> max {density['max']})")
            check(not s["error"], f"{label}: no error ({s['error']})")
            check(s["epoch"] == s["nEpochs"] > 0, f"{label}: ran all epochs ({s['epoch']}/{s['nEpochs']})")
            if args.subsample and count > 2000:
                check(s["nEpochs"] == 60 and page.evaluate("Array.from(window.__reembed.ctl().alpha).every((a) => a > 0.99)"),
                      f"{label}: sampled run refined and all points visible")
                msgs = page.evaluate("window.__msgs")
                placed = min((t for t, role, kind, *_ in msgs if kind == "placed"), default=None)
                sample_epochs = [(e, ne) for t, role, kind, phase, initial, e, ne in msgs
                                 if role == "sample" and kind == "frame" and placed is not None and t < placed]
                check(bool(sample_epochs) and sample_epochs[-1][0] == sample_epochs[-1][1],
                      f"{label}: sample (optimizing everything is slow) finished its schedule before the takeover"
                      + (f" ({sample_epochs[-1][0]}/{sample_epochs[-1][1]})" if sample_epochs else ""))
            if args.slow_link and label == "level1":
                msgs = page.evaluate("window.__msgs")
                plan = page.evaluate("window.__reembed.ctl().plan")
                print(f"{label}: plan sample {plan['sample']}, zoom {plan['zoomMs']:.0f} ms, predicted {plan['fullMs']:.0f} ms")
                moving = [t for t, role, kind, phase, initial, *_ in msgs if role == "sample" and kind == "frame" and not initial]
                full_graph = [t for t, role, kind, *_ in msgs if role == "hold" and kind == "graph"]
                placed = [t for t, role, kind, *_ in msgs if role == "hold" and kind == "placed"]
                check(plan["sample"] > 0 and plan["zoomMs"] > 1100, f"{label}: slow link -> sample first, longer zoom")
                check(bool(moving and full_graph) and moving[0] < full_graph[0],
                      f"{label}: sample moving before the full graph arrived"
                      + (f" ({full_graph[0] - moving[0]:.0f} ms earlier)" if moving and full_graph else ""))
                check(bool(placed) and s["nEpochs"] == 60
                      and page.evaluate("Array.from(window.__reembed.ctl().alpha).every((a) => a > 0.99)"),
                      f"{label}: full optimizer took over, refined, all points visible")
            ids = [l[0] for l in s["layers"]]
            check("reembed-active" in ids and "reembed-ghost" not in ids and "reembed-labels-ghost" not in ids,
                  f"{label}: active points and labels only")
            labels = page.evaluate("""() => {
                const ctl = window.__reembed.ctl(), level = ctl.current(), items = ctl.labels.items;
                const contained = items.every((d) => d.relatedPoints.every((g) => level.local[g] >= 0));
                // Each label sits on one of its member points.
                const onMember = items.every((d) => d._sample.some((i) => ctl.disp[2*i] === d.x && ctl.disp[2*i+1] === d.y));
                const layer = window.datamap.deckgl.props.layers.find((l) => l.id === "reembed-labels");
                return { n: items.length, contained, onMember, layer: !!layer, opacity: layer ? layer.props.opacity : 0,
                         sample: items.slice(0, 3).map((d) => d.label) };
            }""")
            print(f"{label}: {labels['n']} labels, e.g. {labels['sample']}")
            check(labels["n"] > 0 and labels["layer"] and labels["opacity"] == 1, f"{label}: re-embed labels shown")
            check(labels["contained"] and labels["onMember"], f"{label}: labels contained in selection and placed on member points")
            if shots:
                page.screenshot(path=str(shots / f"{label}_done.png"))
            return s

        # Track points that will end up in the nested selection (chosen the same way as lassoNear).
        tracked = page.evaluate("""() => {
            const pos = window.datamap.pointLayer.props.data.attributes.getPosition.value, n = pos.length / 2;
            const c = Math.floor(n * 0.37) % n, d = [];
            for (let i = 0; i < n; i++) d.push([(pos[2*i]-pos[2*c])**2 + (pos[2*i+1]-pos[2*c+1])**2, i]);
            d.sort((a, b) => a[0] - b[0]);
            return d.slice(0, 8).map((x) => x[1]).concat([c]);
        }""")
        page.evaluate(f"window.__reembed.record({json.dumps(tracked)})")
        s1 = run_level(0.25, "level1")
        check(s1["depth"] == 1 and s1["filter"], "level1: depth 1 with layer filter")
        # Hover picking maps back to global ids.
        pick = page.evaluate("""() => {
            const ctl = window.__reembed.ctl();
            const i = 3, x = ctl.disp[2 * i], y = ctl.disp[2 * i + 1];
            const vp = window.datamap.deckgl.viewManager.getViewports()[0];
            const [px, py] = vp.project([x, y]);
            const info = window.datamap.deckgl.pickObject({ x: px, y: py, radius: 2 });
            if (!info) return null;
            const g = window.datamap.pickRemap(info).index;
            const tip = window.datamap.deckgl.props.getTooltip(info);
            return [info.layer.id, info.index, g, ctl.current().ids[info.index],
                    JSON.stringify(tip) === JSON.stringify(window.datamap.tooltipFunction({ index: g }))];
        }""")
        check(pick is not None and pick[0] == "reembed-active" and pick[2] == pick[3], f"level1: pick remaps to global id {pick}")
        check(pick is not None and pick[4], "level1: tooltip shows the picked point's own text")

        def slider_check(label, value):
            """Moving min_dist re-optimizes the shown layout (median NN spacing grows)."""
            spacing = """() => {
                const ctl = window.__reembed.ctl(), p = ctl.disp, n = p.length / 2, d = [];
                for (let i = 0; i < Math.min(n, 600); i++) {
                    let best = Infinity;
                    for (let j = 0; j < n; j++) if (j !== i) best = Math.min(best, (p[2*i]-p[2*j])**2 + (p[2*i+1]-p[2*j+1])**2);
                    d.push(Math.sqrt(best));
                }
                d.sort((a, b) => a - b);
                return d[d.length >> 1] / (ctl.levels[ctl.depth].fitIdx ? 1 : 1);
            }"""
            before = page.evaluate(spacing)
            page.evaluate(f"""() => {{
                const el = document.querySelector('.reembed-min-dist');
                el.value = {value}; el.dispatchEvent(new Event('input'));
            }}""")
            page.wait_for_function("window.__reembed.state().mode === 'running'", timeout=5000)
            page.wait_for_function("window.__reembed.state().mode === 'idle' && window.__reembed.state().phase === 'done'", timeout=60000)
            s = state()
            after = page.evaluate(spacing)
            print(f"{label}: min_dist -> {value}: median NN spacing {before:.4g} -> {after:.4g}")
            check(s["epoch"] == s["nEpochs"] > 0 and not s["error"], f"{label}: slider re-optimized ({s['epoch']}/{s['nEpochs']})")
            check(after > 1.2 * before, f"{label}: larger min_dist spreads the layout")

        slider_check("level1", 0.6)
        page.evaluate("() => { const el = document.querySelector('.reembed-min-dist'); el.value = 0.1; el.dispatchEvent(new Event('input')); }")
        page.wait_for_function("window.__reembed.state().mode === 'idle' && window.__reembed.state().phase === 'done'", timeout=60000)

        before_level2 = state()
        s2 = run_level(0.3, "level2")
        check(s2["depth"] == 2, "level2: nested depth 2")

        page.click(".reembed-back")
        try:
            page.wait_for_function("window.__reembed.state().depth === 1 && !window.__reembed.state().transition", timeout=10000)
        except Exception:
            print(json.dumps(state())[:2000])
            print(errors[:5])
            raise
        s3 = state()
        check(all(abs(s3["view"][k] - before_level2["view"][k]) < 1e-6 for k in ("longitude", "latitude", "zoom")), "back to level1: camera restored")
        check(page.evaluate("window.__reembed.ctl().worker === null && window.__reembed.ctl().holdWorker === null"), "back to level1: child workers stopped")
        slider_check("level1 after back (respawned worker)", 0.6)
        if shots:
            page.screenshot(path=str(shots / "back1.png"))
        # Sample the label layer's opacity as deck.gl sees it while returning to the full map
        # (transitions slowed down, as headless software rendering can be only a few fps).
        page.evaluate("""() => {
            const ctl = window.__reembed.ctl(), start = ctl._startTransition.bind(ctl);
            ctl._startTransition = (tr) => start({ ...tr, dur: tr.dur * 4 });
            const out = (window.__labelOpacity = []);
            let sampling = true;
            window.__restoreTransitions = () => { delete ctl._startTransition; sampling = false; };
            const step = () => {
                const layer = (window.datamap.deckgl.props.layers || []).find((l) => l.id === "labelLayer");
                if (layer) out.push(layer.props.opacity);
                if (sampling) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
        }""")
        page.click(".reembed-back")
        page.wait_for_function("window.__reembed.state().depth === 0 && !window.__reembed.state().transition", timeout=20000)
        page.wait_for_timeout(200)
        page.evaluate("window.__restoreTransitions()")
        s4 = state()
        label_opacity = page.evaluate("window.__labelOpacity")
        check(any(0.05 < o < 0.95 for o in label_opacity), "root: labels fade back in (deck.gl sees intermediate opacity)")
        motion = analyse_motion(page.evaluate("window.__reembed.stopRecording()"))
        print(f"motion: {motion['frames']} frames, max per-frame jump {motion['maxFrameJumpPx']} px")
        for snap in motion["snaps"]:
            print(f"  snap {snap['from']} -> {snap['to']}: jump {snap['jumpPx']} px, radius change {snap['radiusChangePx']} px")
        check(len(motion["snaps"]) == 4, "four camera snaps (2 zoom-ins, 2 backs)")
        check(all(s["jumpPx"] is not None and s["jumpPx"] < 0.5 and s["radiusChangePx"] < 0.05 for s in motion["snaps"]),
              "camera snaps are invisible (< 0.5 px, < 0.05 px radius)")
        if shots:
            page.screenshot(path=str(shots / "back0.png"))
        check(not s4["filter"], "root: layer filter removed")
        check(not any(l[0].startswith("reembed-") for l in s4["layers"]), "root: re-embed layers removed")
        if s4["layers"] != s0["layers"]:
            print("root layers before:", s0["layers"])
            print("root layers after: ", s4["layers"])
        check(s4["layers"] == s0["layers"], f"root: layers and opacities restored")
        check(all(abs(s4["view"][k] - s0["view"][k]) < 1e-6 for k in ("longitude", "latitude", "zoom")), "root: camera restored")

        # Back while the kNN request is still in flight must not leave a worker behind.
        page.evaluate("""() => {
            const fetch0 = window.fetch;
            window.fetch = (...a) => new Promise((r) => setTimeout(r, 1800)).then(() => fetch0(...a));
            window.__restoreFetch = () => { window.fetch = fetch0; };
        }""")
        page.evaluate("window.__reembed.lassoNear(0.1)")
        page.wait_for_timeout(150)
        page.click(".reembed-go")
        page.wait_for_function("window.__reembed.state().mode === 'running'", timeout=10000)
        page.click(".reembed-back")
        page.wait_for_function("window.__reembed.state().depth === 0 && !window.__reembed.state().transition", timeout=10000)
        page.wait_for_timeout(2500)
        check(page.evaluate("window.__reembed.ctl().worker === null && window.__reembed.ctl().holdWorker === null"), "back during request: no orphaned worker")
        page.evaluate("window.__restoreFetch()")
        browser.close()

    server.stop()
    errors = [e for e in errors if "did not load within" not in e]  # headless font timeout
    check(not errors, f"no console errors {json.dumps(errors[:5])}")
    print("PASS" if not failures else f"FAILED: {len(failures)} checks")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
