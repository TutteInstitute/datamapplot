"""End-to-end check of the ReembedWidget in a JupyterLab notebook (developer script).

Writes a notebook that starts a ReembedServer in its kernel and shows a 20
Newsgroups data map with ``ReembedWidget(server=server)``, serves it with
JupyterLab under a JupyterHub-like base URL, runs it in headless Chromium and
checks that the widget reaches the server through jupyter-server-proxy
(``<base url>proxy/<port>``; with ``--no-proxy``, the extension is disabled and
the widget must fall back to the server's direct address), then re-embeds a
lasso selection and goes back.

    python scripts/reembed_notebook_e2e.py [--data ng20.parquet] [--no-proxy] [--headed]

Requires jupyterlab, jupyter-server-proxy, ipykernel, pynndescent and playwright.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import nbformat

sys.path.insert(0, str(Path(__file__).parent))
from reembed_e2e import DATA_URL, HELPERS  # noqa: E402

TOKEN = "e2e-jupyter-token"
SERVER_TOKEN = "e2e-reembed-token"
BASE_URL = "/user/test/"


def notebook(data):
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nb.cells = [
        nbformat.v4.new_code_cell(f"""\
import numpy as np
import pandas as pd
import datamapplot
from datamapplot.reembed_server import ReembedServer

df = pd.read_parquet({data!r})
vectors = np.stack(df["embedding"].values).astype(np.float32)
server = ReembedServer(vectors, metric="cosine", token={SERVER_TOKEN!r}, verbose=False).start()
print("REEMBED_PORT", server.port)"""),
        nbformat.v4.new_code_cell("""\
datamapplot.create_interactive_plot(
    np.stack(df["map"].values),
    *[df[f"layer_{i}_topics"].values for i in range(5)],
    hover_text=df["post"].str.slice(0, 120).values,
    widgets=[datamapplot.ReembedWidget(server=server, engine="cpu")],
)"""),
    ]
    return nb


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_plot_frame(page, timeout_s):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for frame in page.frames:
            try:
                if frame.evaluate("!!(window.datamap && window.datamap.widgets && window.datamap.widgets.reembed)"):
                    return frame
            except Exception:
                pass
        time.sleep(1)
    raise TimeoutError("the plot's frame did not appear")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=None, help="local copy of the 20 Newsgroups topics parquet")
    parser.add_argument("--no-proxy", action="store_true", help="disable jupyter-server-proxy")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    failures, errors = [], []

    def check(cond, message):
        print(("  ok   " if cond else "  FAIL ") + message)
        if not cond:
            failures.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data = os.path.abspath(args.data) if args.data else DATA_URL
        nbformat.write(notebook(data), tmp / "reembed.ipynb")
        port = free_port()
        env = {**os.environ, "JUPYTER_CONFIG_DIR": str(tmp / "config"), "JUPYTER_RUNTIME_DIR": str(tmp / "runtime")}
        command = [
            sys.executable, "-m", "jupyter", "lab", "--no-browser", f"--port={port}", "--ServerApp.ip=127.0.0.1",
            f"--ServerApp.base_url={BASE_URL}", f"--IdentityProvider.token={TOKEN}", f"--ServerApp.root_dir={tmp}",
            "--LabApp.expose_app_in_browser=True",
        ]
        if args.no_proxy:
            command.append('--ServerApp.jpserver_extensions={"jupyter_server_proxy": False}')
        lab = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=open(tmp / "lab.log", "w"))
        root = f"http://127.0.0.1:{port}{BASE_URL}"
        try:
            for _ in range(120):
                try:
                    urllib.request.urlopen(f"{root}api/status?token={TOKEN}", timeout=2)
                    break
                except Exception:
                    time.sleep(0.5)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=not args.headed)
                page = browser.new_page(viewport={"width": 1400, "height": 1000})
                page.on("console", lambda m: m.type == "error" and errors.append((m.text, m.location.get("url", ""))))
                page.on("pageerror", lambda e: errors.append((str(e), "")))
                page.goto(f"{root}lab/tree/reembed.ipynb?token={TOKEN}")
                page.wait_for_selector(".jp-Notebook .jp-Cell", timeout=120000)
                page.wait_for_selector(".jp-Notebook-ExecutionIndicator[data-status='idle']", timeout=120000)
                page.wait_for_function("window.jupyterapp && window.jupyterapp.commands.isEnabled('notebook:run-all-cells')",
                                       timeout=120000)
                # Run the cells once the kernel is connected (earlier requests can be dropped).
                page.wait_for_function("""async () => {
                    const context = window.jupyterapp.shell.currentWidget.sessionContext;
                    await context.ready;
                    const kernel = context.session && context.session.kernel;
                    return !!kernel && kernel.connectionStatus === "connected" && kernel.status === "idle";
                }""", timeout=120000, polling=500)
                for _ in range(5):
                    page.evaluate("window.jupyterapp.commands.execute('notebook:run-all-cells')")
                    try:
                        page.wait_for_function("/\\[(\\*|\\d+)\\]/.test(document.querySelector('.jp-Cell .jp-InputPrompt').textContent)",
                                               timeout=20000)
                        break
                    except Exception:
                        print("cells did not start; retrying")

                try:
                    frame = find_plot_frame(page, 300)
                except TimeoutError:
                    page.screenshot(path=str(Path(tempfile.gettempdir()) / "reembed_notebook_e2e.png"))
                    print("outputs:", [t[:300] for t in page.locator(".jp-OutputArea-output").all_inner_texts()])
                    print("lab log:", (tmp / "lab.log").read_text()[-2000:])
                    raise
                server_port = int(page.locator(".jp-OutputArea-output", has_text="REEMBED_PORT").first.inner_text().split()[-1])
                frame.evaluate(HELPERS)
                frame.wait_for_function("window.__reembed.ctl().server && ['ready', 'mismatch'].includes(window.__reembed.ctl().server.stage)",
                                        timeout=180000, polling=500)
                base = frame.evaluate("window.__reembed.ctl().base")
                expected = f"http://127.0.0.1:{server_port}" if args.no_proxy else f"{root}proxy/{server_port}"
                print(f"widget uses {base}")
                check(base == expected, f"server found at {expected}" + (" (proxy disabled)" if args.no_proxy else " (through Jupyter)"))

                frame.evaluate("window.__reembed.lassoNear(0.25)")
                frame.wait_for_timeout(300)
                count = frame.evaluate("window.__reembed.ctl().selectionCount")
                frame.evaluate("document.querySelector('.reembed-go').click()")
                frame.wait_for_function("window.__reembed.state().phase === 'done' || !!window.__reembed.state().error",
                                        timeout=180000, polling=250)
                s = frame.evaluate("window.__reembed.state()")
                print(f"re-embed {count} points: {s['statusText']}")
                check(not s["error"] and s["epoch"] == s["nEpochs"] > 0, f"re-embedded {count} points ({s['error']})")
                frame.wait_for_function("window.__reembed.state().mode === 'idle'", timeout=30000)
                frame.evaluate("document.querySelector('.reembed-back').click()")
                frame.wait_for_function("window.__reembed.state().depth === 0 && window.__reembed.state().mode === 'idle'",
                                        timeout=30000)
                check(True, "back to the full map")
                # Without the proxy, probing it logs a 404 (browsers log failed requests), as
                # does JupyterLab's own server-proxy extension.
                relevant = [text for text, url in errors if "Font" not in text
                            and not (args.no_proxy and "404" in text and "proxy/" in url)]
                if errors:
                    print("console errors:", errors[:4])
                check(not relevant, f"no console errors {relevant[:3]}")
                browser.close()
        finally:
            lab.terminate()
            lab.wait(30)
    print("PASS" if not failures else f"FAILED: {len(failures)} checks")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
