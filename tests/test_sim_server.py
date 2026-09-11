# -*- coding: utf-8 -*-
import asyncio
import json
import os
import socket
import tempfile
import threading
import time
import unittest

import aiohttp
from aiohttp import web

from sim.overlay_client import healthy, post_overlay
from sim.range_server import create_app


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class SimServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.port = _free_port()
        app = create_app(out_dir=self.tmp.name, width=320, height=320, count=2,
                         tick_hz=200, log_hz=200, seed=1)
        self.ready = threading.Event()
        self.loop = None

        def run():
            if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            runner = web.AppRunner(app)
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, "127.0.0.1", self.port)
            loop.run_until_complete(site.start())
            self.ready.set()
            loop.run_forever()
            loop.run_until_complete(runner.cleanup())
            loop.close()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self.assertTrue(self.ready.wait(5))
        for _ in range(50):
            if healthy(self.port):
                break
            time.sleep(0.1)
        else:
            self.fail("server not healthy")

    def tearDown(self):
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        self.tmp.cleanup()

    def _read_lines(self, name):
        path = os.path.join(self.tmp.name, name)
        if not os.path.isfile(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return [line for line in f if line.strip()]

    def test_health_overlay_and_logs(self):
        self.assertTrue(post_overlay(self.port, {"boxes": [[1, 2, 3, 4]], "input_w": 320}))
        time.sleep(0.5)
        self.assertTrue(self._read_lines("truth.jsonl"))
        overlay_lines = self._read_lines("overlay.jsonl")
        self.assertTrue(overlay_lines)
        rec = json.loads(overlay_lines[-1])
        self.assertEqual(rec["boxes"], [[1, 2, 3, 4]])

    def test_ws_config(self):
        async def go():
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"http://127.0.0.1:{self.port}/ws") as ws:
                    return await asyncio.wait_for(ws.receive_json(), timeout=3)

        msg = asyncio.run(go())
        self.assertEqual(msg["type"], "config")
        self.assertEqual(msg["config"]["width"], 320)

    def test_static_page_served(self):
        async def go():
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{self.port}/") as r:
                    html = await r.text()
                async with session.get(f"http://127.0.0.1:{self.port}/static/range.js") as r2:
                    js = await r2.text()
                return html, js

        html, js = asyncio.run(go())
        self.assertIn("canvas", html)
        self.assertIn("mouse_delta", js)


if __name__ == "__main__":
    unittest.main()
