#!/usr/bin/env python3
"""MCP server that exposes ADB tools so Claude can interact with Android emulators/devices."""

import subprocess
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

mcp = FastMCP("adb-interaction", host="0.0.0.0", port=8755)


# ─── Internal helper ──────────────────────────────────────────────────────────

def _adb(*args: str, device: str = "", timeout: int = 30) -> tuple[str, str, int]:
    cmd = ["adb"]
    if device:
        cmd += ["-s", device]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


# ─── Device management ────────────────────────────────────────────────────────

@mcp.tool()
def list_devices() -> str:
    """List all ADB-connected devices and emulators with their state."""
    stdout, _, _ = _adb("devices", "-l")
    return stdout


@mcp.tool()
def get_app_pid(package_name: str, device: str = "") -> str:
    """Check if an app is running. Returns the PID or 'not running'."""
    stdout, _, _ = _adb("shell", "pidof", package_name, device=device)
    return stdout if stdout else "not running"


@mcp.tool()
def current_activity(device: str = "") -> str:
    """Return the package and activity currently in the foreground."""
    stdout, _, _ = _adb("shell", "dumpsys", "window", "windows", device=device)
    for line in stdout.splitlines():
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            return line.strip()
    return "Could not determine current activity"


# ─── Screen capture ───────────────────────────────────────────────────────────

@mcp.tool()
def take_screenshot(device: str = "") -> Image:
    """
    Capture the current screen and return it as an image.
    Claude can see the screenshot and reason about what is on screen.
    """
    remote = "/sdcard/adb_mcp_screen.png"

    _, stderr, rc = _adb("shell", "screencap", "-p", remote, device=device)
    if rc != 0:
        raise RuntimeError(f"screencap failed: {stderr}")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        local = f.name

    try:
        _, stderr, rc = _adb("pull", remote, local, device=device)
        if rc != 0:
            raise RuntimeError(f"adb pull failed: {stderr}")
        return Image(data=Path(local).read_bytes(), format="png")
    finally:
        Path(local).unlink(missing_ok=True)


@mcp.tool()
def dump_ui(device: str = "") -> str:
    """
    Dump the full UI hierarchy of the current screen as XML.
    Useful for finding element bounds, resource-ids, and text without needing coordinates.
    """
    remote = "/sdcard/adb_mcp_ui.xml"

    _, stderr, rc = _adb("shell", "uiautomator", "dump", remote, device=device)
    if rc != 0:
        raise RuntimeError(f"uiautomator dump failed: {stderr}")

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="w") as f:
        local = f.name

    try:
        _, stderr, rc = _adb("pull", remote, local, device=device)
        if rc != 0:
            raise RuntimeError(f"adb pull failed: {stderr}")
        return Path(local).read_text()
    finally:
        Path(local).unlink(missing_ok=True)


# ─── android-cli tools (token-efficient alternatives) ─────────────────────────

_ANNOTATED_PATH = Path(tempfile.gettempdir()) / "adb_mcp_annotated.png"


def _android(*args: str, timeout: int = 30) -> tuple[str, str, int]:
    cmd = ["android"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip(), result.stderr.strip(), result.returncode


@mcp.tool()
def get_layout(diff: bool = False) -> str:
    """
    Get the current screen UI layout as JSON via android-cli.
    Prefer over dump_ui — JSON is more compact than XML.
    Set diff=True to return only elements that changed since the last get_layout call.
    Requires android-cli (https://developer.android.com/tools/agents/android-cli).
    """
    args = ["layout"]
    if diff:
        args.append("--diff")
    stdout, stderr, rc = _android(*args)
    if rc != 0:
        raise RuntimeError(f"android layout failed: {stderr}")
    return stdout or "(empty layout)"


@mcp.tool()
def take_annotated_screenshot() -> Image:
    """
    Capture a screenshot with numbered bounding boxes around every detected UI element.
    Pair with resolve_coordinates to get tap targets by label number — no coordinate math needed.
    Requires android-cli (https://developer.android.com/tools/agents/android-cli).
    """
    _, stderr, rc = _android(
        "screen", "capture", "--annotate", f"--output={_ANNOTATED_PATH}",
    )
    if rc != 0:
        raise RuntimeError(f"android screen capture --annotate failed: {stderr}")
    return Image(data=_ANNOTATED_PATH.read_bytes(), format="png")


@mcp.tool()
def resolve_coordinates(query: str) -> str:
    """
    Resolve #N placeholders to real screen coordinates using the last annotated screenshot.
    Must call take_annotated_screenshot first.
    Example: resolve_coordinates("input tap #3") → "input tap 540 1200"
    Requires android-cli (https://developer.android.com/tools/agents/android-cli).
    """
    if not _ANNOTATED_PATH.exists():
        raise RuntimeError("No annotated screenshot — call take_annotated_screenshot first")
    stdout, stderr, rc = _android(
        "screen", "resolve",
        f"--screenshot={_ANNOTATED_PATH}",
        f"--string={query}",
    )
    if rc != 0:
        raise RuntimeError(f"android screen resolve failed: {stderr}")
    return stdout or "(no resolved coordinates)"


# ─── Input ────────────────────────────────────────────────────────────────────

@mcp.tool()
def tap(x: int, y: int, device: str = "") -> str:
    """Tap at screen coordinates (x, y)."""
    _, stderr, rc = _adb("shell", "input", "tap", str(x), str(y), device=device)
    if rc != 0:
        raise RuntimeError(f"tap failed: {stderr}")
    return f"Tapped ({x}, {y})"


@mcp.tool()
def long_press(x: int, y: int, duration_ms: int = 1000, device: str = "") -> str:
    """Long-press at coordinates (x, y) for duration_ms milliseconds."""
    _, stderr, rc = _adb(
        "shell", "input", "swipe",
        str(x), str(y), str(x), str(y), str(duration_ms),
        device=device,
    )
    if rc != 0:
        raise RuntimeError(f"long_press failed: {stderr}")
    return f"Long-pressed ({x}, {y}) for {duration_ms}ms"


@mcp.tool()
def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300, device: str = "") -> str:
    """Swipe from (x1, y1) to (x2, y2) over duration_ms milliseconds."""
    _, stderr, rc = _adb(
        "shell", "input", "swipe",
        str(x1), str(y1), str(x2), str(y2), str(duration_ms),
        device=device,
    )
    if rc != 0:
        raise RuntimeError(f"swipe failed: {stderr}")
    return f"Swiped ({x1},{y1}) → ({x2},{y2})"


@mcp.tool()
def input_text(text: str, device: str = "") -> str:
    """
    Type text into the currently focused field.
    Tap the field first to focus it, then call this tool.
    Note: special characters may need escaping; use press_key('DEL') to delete.
    """
    escaped = text.replace("\\", "\\\\").replace(" ", "%s").replace("'", "\\'")
    _, stderr, rc = _adb("shell", "input", "text", escaped, device=device)
    if rc != 0:
        raise RuntimeError(f"input text failed: {stderr}")
    return f"Typed: {text}"


@mcp.tool()
def press_key(keycode: str, device: str = "") -> str:
    """
    Press a key by name. Common keys:
      BACK, HOME, ENTER, DEL, TAB, SPACE, ESCAPE, APP_SWITCH,
      DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT,
      VOLUME_UP, VOLUME_DOWN, POWER.
    """
    key = keycode.upper()
    if not key.startswith("KEYCODE_"):
        key = f"KEYCODE_{key}"
    _, stderr, rc = _adb("shell", "input", "keyevent", key, device=device)
    if rc != 0:
        raise RuntimeError(f"keyevent failed: {stderr}")
    return f"Pressed {key}"


# ─── Logs ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_logcat(
    lines: int = 100,
    package: str = "",
    level: str = "D",
    device: str = "",
) -> str:
    """
    Get recent logcat output.

    Args:
        lines:   Number of recent lines to return (default 100).
        package: Optional app package name to filter output.
        level:   Minimum log level — V, D, I, W, E (default D).
        device:  Target device serial (empty = default device).
    """
    stdout, stderr, rc = _adb("logcat", "-d", "-t", str(lines), device=device)
    if rc != 0:
        raise RuntimeError(f"logcat failed: {stderr}")

    output = stdout
    if package:
        output = "\n".join(
            line for line in stdout.splitlines()
            if package in line or line.startswith("-----")
        )

    return output or "(no output)"


@mcp.tool()
def clear_logcat(device: str = "") -> str:
    """Clear the logcat buffer so subsequent get_logcat calls only show new messages."""
    _, stderr, rc = _adb("logcat", "-c", device=device)
    if rc != 0:
        raise RuntimeError(f"clear logcat failed: {stderr}")
    return "Logcat buffer cleared"


# ─── App lifecycle ────────────────────────────────────────────────────────────

@mcp.tool()
def launch_app(package_name: str, device: str = "") -> str:
    """Launch an app by package name."""
    _, stderr, rc = _adb(
        "shell", "monkey",
        "-p", package_name,
        "-c", "android.intent.category.LAUNCHER",
        "1",
        device=device,
    )
    if rc != 0:
        raise RuntimeError(f"launch failed: {stderr}")
    return f"Launched {package_name}"


@mcp.tool()
def install_apk(apk_path: str, device: str = "") -> str:
    """
    Install an APK onto the device using streaming mode.
    Accepts test-only APKs (debug builds) and replaces any existing installation.
    apk_path must be an absolute path on the host machine.
    """
    _, stderr, rc = _adb("install", "-r", "-t", "--streaming", apk_path, device=device, timeout=120)
    if rc != 0:
        raise RuntimeError(f"install failed: {stderr}")
    return f"Installed {apk_path}"


@mcp.tool()
def stop_app(package_name: str, device: str = "") -> str:
    """Force-stop an app by package name."""
    _, stderr, rc = _adb("shell", "am", "force-stop", package_name, device=device)
    if rc != 0:
        raise RuntimeError(f"force-stop failed: {stderr}")
    return f"Stopped {package_name}"


@mcp.tool()
def start_activity(activity: str, device: str = "") -> str:
    """
    Start a specific activity. Use fully qualified name, e.g.:
      com.medrepasse/.ui.MainActivity
      com.medrepasse/com.medrepasse.ui.sign.SignInActivity
    """
    _, stderr, rc = _adb("shell", "am", "start", "-n", activity, device=device)
    if rc != 0:
        raise RuntimeError(f"start activity failed: {stderr}")
    return f"Started {activity}"


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
