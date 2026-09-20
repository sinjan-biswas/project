# backend/services/enhancement_service.py
"""
Lazy-install enhancement service.

Pipeline order (cheap → expensive):
    dewarp   → rectifies tilted / warped documents
    zero_dce → brightens dark captures
    esrgan   → 4x upscale + deblur

Each tool gets its own venv (uv-managed) and its own Python version.
A `.setup_complete` marker gates re-install on subsequent runs.
"""

import asyncio
import os
import re
import shlex
import shutil
import tempfile

# ---------------------------------------------------------------------------
# Paths — enhancers live at  project/enhancers/  (sibling of backend/)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
ENHANCERS = os.path.abspath(os.path.join(_HERE, "..", "..", "enhancers"))

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
TOOLS = {
    "dewarp": {
        # ICCV 2023 — Foreground & Text-lines Aware Document Image Rectification
        "repo_url": "https://github.com/xiaomore/Document-Image-Dewarping.git",
        "dir": "Document-Image-Dewarping",
        # predict.py wants a DIRECTORY of images and writes <name>.png per image.
        # The "{inp}.in" placeholder is expanded in _run() to a sibling folder.
        "inference_cmd": (
            "./venv/bin/python predict.py "
            "--model_path pretrained_models/30.pt "
            "--img_path {inp}.in --save_path {out}"
        ),
        "pip_target": "requirements.txt",
        "fallback_deps": None,
        "python_version": "3.10",
        "requirement_fixes": {
            r"^torch==1\.13\.0\+cu117$":       "torch==1.13.0",
            r"^torchvision==0\.14\.0\+cu117$": "torchvision==0.14.0",
        },
        "post_install_cmds": [],
    },
    "zero_dce": {
        "repo_url": "https://github.com/raspberrypi/AI_enhance.git",
        "dir": "AI_enhance",
        "inference_cmd": (
            "./venv/bin/python enhance_dcenet.py "
            "{inp} {out}/enhanced.png"
        ),
        "pip_target": "requirements.txt",
        "fallback_deps": [
            "torch", "torchvision", "numpy",
            "opencv-python", "pillow", "ai-edge-litert",
        ],
        "python_version": None,
        "requirement_fixes": {},
        "post_install_cmds": [],
    },
    "esrgan": {
        "repo_url": "https://github.com/xinntao/Real-ESRGAN.git",
        "dir": "Real-ESRGAN",
        "inference_cmd": (
            "./venv/bin/python inference_realesrgan.py "
            "-n RealESRGAN_x4plus -i {inp} -o {out} -t 256" 
        ),
        "pip_target": "requirements.txt",
        "fallback_deps": None,
        "python_version": None,
        "requirement_fixes": {},
        "post_install_cmds": [
            "VIRTUAL_ENV=venv uv pip install -e .",
            "sed -i "
            "'s/from torchvision.transforms.functional_tensor import rgb_to_grayscale/"
            "from torchvision.transforms.functional import rgb_to_grayscale/' "
            "venv/lib/python*/site-packages/basicsr/data/degradations.py",
        ],
    },
}

SETUP_TIMEOUT_S = 1800
INFERENCE_TIMEOUT_S = 120


class EnhancementService:
    def __init__(self, enabled: bool = True, auto_setup: bool = True):
        self.enabled = enabled
        self.auto_setup = auto_setup
        # Lazy lock creation — avoids "different event loop" errors
        # when the service is imported at module level.
        self._setup_locks: dict[str, asyncio.Lock] = {}
        self._lock_guard = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    async def enhance(self, image_bytes: bytes, quality: dict) -> tuple[bytes, bool]:
        if not self.enabled:
            return image_bytes, False

        current = image_bytes
        changed = False
        m = quality.get("metrics", {})

        # Dewarp / rectify if tilted or blurry
        if abs(m.get("skew_deg", 0)) > 8 or m.get("blur_var", 999) < 150:
            new = await self._run("dewarp", current)
            changed = changed or (new != current)
            current = new

        # Low-light enhancement if too dark
        if m.get("dark_pct", 0) > 40:
            new = await self._run("zero_dce", current)
            changed = changed or (new != current)
            current = new

        # Upscale / deblur if resolution is low or still blurry
        if m.get("width", 2000) < 1000 or m.get("blur_var", 999) < 120:
            new = await self._run("esrgan", current)
            changed = changed or (new != current)
            current = new

        return current, changed

    async def warmup(self) -> dict:
        """Pre-install every tool. Safe to call at startup."""
        results = {}
        for tool in TOOLS:
            try:
                await self._ensure_tool(tool)
                results[tool] = True
            except Exception as e:
                print(f"[enhancer] warmup failed for {tool}: {e}")
                results[tool] = False
        return results

    # ------------------------------------------------------------------
    # Ensure a tool is cloned + has a working venv + marker
    # ------------------------------------------------------------------
    async def _ensure_tool(self, tool: str) -> str:
        meta = TOOLS[tool]
        tool_dir = os.path.join(ENHANCERS, meta["dir"])
        marker = os.path.join(tool_dir, ".setup_complete")

        # Fast path — fully installed (venv + deps).
        if os.path.exists(marker):
            return tool_dir

        if not self.auto_setup:
            raise RuntimeError(
                f"{meta['dir']} is not set up at {tool_dir} "
                f"and auto_setup is disabled."
            )

        lock = await self._get_lock(tool)
        async with lock:
            if os.path.exists(marker):
                return tool_dir

            os.makedirs(ENHANCERS, exist_ok=True)

            # 1. Clone (skip if folder already exists)
            if not os.path.isdir(tool_dir):
                print(f"[enhancer] cloning {meta['dir']} ...")
                code = await self._shell(
                    f"git clone {shlex.quote(meta['repo_url'])} "
                    f"{shlex.quote(meta['dir'])}",
                    cwd=ENHANCERS,
                    timeout=SETUP_TIMEOUT_S,
                )
                if code != 0:
                    raise RuntimeError(f"git clone failed for {meta['dir']}")
            else:
                print(f"[enhancer] {meta['dir']} already cloned, skipping git")

            # 2. Create venv with uv, optionally pinned to a specific Python.
            venv_python = os.path.join(tool_dir, "venv", "bin", "python")
            if not os.path.exists(venv_python):
                py_ver = meta.get("python_version")
                py_flag = f" --python {shlex.quote(py_ver)}" if py_ver else ""
                print(f"[enhancer] creating venv for {meta['dir']} using uv"
                      f"{f' (Python {py_ver})' if py_ver else ''} ...")
                code = await self._shell(
                    f"uv venv venv{py_flag}",
                    cwd=tool_dir,
                    timeout=SETUP_TIMEOUT_S,
                )
                if code != 0:
                    raise RuntimeError(f"uv venv failed for {meta['dir']}")

            # 3. Install requirements (or fallback deps) via uv.
            pip_target = meta["pip_target"]
            req_path = os.path.join(tool_dir, pip_target)

            if os.path.exists(req_path):
                install_rel = self._sanitize_requirements(
                    req_path, meta.get("requirement_fixes") or {}
                )
                print(f"[enhancer] installing {install_rel} for {meta['dir']} "
                      f"using uv (this can take several minutes) ...")
                code = await self._shell(
                    f"VIRTUAL_ENV=venv uv pip install -r {shlex.quote(install_rel)}",
                    cwd=tool_dir,
                    timeout=SETUP_TIMEOUT_S,
                )
                if code != 0:
                    raise RuntimeError(
                        f"uv pip install failed for {meta['dir']} (see log above)"
                    )
            elif meta.get("fallback_deps"):
                deps = " ".join(shlex.quote(d) for d in meta["fallback_deps"])
                print(f"[enhancer] no {pip_target} in {meta['dir']} — "
                      f"installing fallback deps: {deps}")
                code = await self._shell(
                    f"VIRTUAL_ENV=venv uv pip install {deps}",
                    cwd=tool_dir,
                    timeout=SETUP_TIMEOUT_S,
                )
                if code != 0:
                    raise RuntimeError(
                        f"uv pip install (fallback) failed for {meta['dir']}"
                    )
            else:
                print(f"[enhancer] WARNING: no {pip_target} in {meta['dir']} "
                      f"and no fallback deps — skipping install")

            # 4. Run any post-install fix commands.
            for cmd in meta.get("post_install_cmds", []):
                print(f"[enhancer] post-install patch for {meta['dir']}: {cmd}")
                code = await self._shell(cmd, cwd=tool_dir, timeout=300)
                if code != 0:
                    print(f"[enhancer] WARNING: post-install patch exited {code}")

            # 5. Mark setup complete.
            with open(marker, "w") as f:
                f.write("ok\n")
            print(f"[enhancer] {meta['dir']} ready at {tool_dir}")
            return tool_dir

    # ------------------------------------------------------------------
    # Sanitize requirements.txt (rewrite/delete broken lines)
    # ------------------------------------------------------------------
    def _sanitize_requirements(self, req_path: str, fixes: dict) -> str:
        if not fixes:
            return os.path.basename(req_path)

        with open(req_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        any_change = False
        for line in lines:
            stripped = line.rstrip("\n")
            replaced = stripped
            deleted = False
            for pat, repl in fixes.items():
                if re.match(pat, stripped):
                    print(f"[enhancer] rewriting requirements line: "
                          f"{stripped!r} -> {repl!r}")
                    replaced = repl
                    deleted = (repl == "")
                    any_change = True
                    break
            if deleted:
                continue
            new_lines.append(replaced + "\n")

        out_name = os.path.basename(req_path) + ".sanitized"
        out_path = os.path.join(os.path.dirname(req_path), out_name)

        if not any_change:
            print(f"[enhancer] no requirement fixes matched in {req_path}, "
                  f"using original")

        with open(out_path, "w") as f:
            f.writelines(new_lines)
        return out_name

    # ------------------------------------------------------------------
    # Run a tool on one image
    # ------------------------------------------------------------------
    async def _run(self, tool: str, img_bytes: bytes) -> bytes:
        try:
            tool_dir = await self._ensure_tool(tool)
        except Exception as e:
            print(f"[enhancer] setup failed for {tool}: {e}")
            return img_bytes  # fall through — gate will decide

        with tempfile.TemporaryDirectory() as tmp:
            inp = os.path.join(tmp, "in.jpg")
            out = os.path.join(tmp, "out")
            os.makedirs(out, exist_ok=True)

            with open(inp, "wb") as f:
                f.write(img_bytes)

            # --- Build the command --------------------------------------
            # Most tools take a single file path. `dewarp`'s predict.py
            # takes a DIRECTORY of images and writes <name>.png into
            # save_path. We materialise a sibling folder `{inp}.in/`
            # with the image inside it.
            if tool == "dewarp":
                in_dir = inp + ".in"
                os.makedirs(in_dir, exist_ok=True)
                shutil.copy(inp, os.path.join(in_dir, "in.jpg"))
                cmd = TOOLS[tool]["inference_cmd"].format(
                    inp=shlex.quote(inp),
                    out=shlex.quote(out),
                )
                # Swap the "{inp}.in" placeholder for the real folder path.
                cmd = cmd.replace(shlex.quote(inp) + ".in", shlex.quote(in_dir))
            else:
                cmd = TOOLS[tool]["inference_cmd"].format(
                    inp=shlex.quote(inp),
                    out=shlex.quote(out),
                )

            print(f"[enhancer] running {tool}: {cmd}")
            code = await self._shell(cmd, cwd=tool_dir,
                                     timeout=INFERENCE_TIMEOUT_S)

            if code != 0:
                print(f"[enhancer] {tool} exited with code {code}, "
                      f"returning original")
                return img_bytes

            produced = [
                f for f in os.listdir(out)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            if not produced:
                print(f"[enhancer] {tool} produced no output, "
                      f"returning original")
                return img_bytes

            with open(os.path.join(out, produced[0]), "rb") as f:
                return f.read()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_lock(self, tool: str) -> asyncio.Lock:
        async with self._lock_guard:
            if tool not in self._setup_locks:
                self._setup_locks[tool] = asyncio.Lock()
            return self._setup_locks[tool]

    async def _shell(self, cmd: str, cwd: str,
                     timeout: float | None = None) -> int:
        """Run a shell command, stream stdout/stderr, return exit code."""
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async def _drain() -> None:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                print(f"[enhancer] {line.decode(errors='replace').rstrip()}")

        try:
            if timeout is None:
                await _drain()
                return await proc.wait()
            await asyncio.wait_for(_drain(), timeout=timeout)
            return await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            print(f"[enhancer] command timed out after {timeout}s, killing")
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return -1