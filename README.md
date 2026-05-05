# adb-interaction-mcp

MCP server that lets Claude Code control Android emulators and real devices via ADB. It exposes 23 tools for screenshots, UI inspection, input simulation, app lifecycle management, and logcat access.

## Prerequisites

- Python ≥ 3.10
- [`uv`](https://docs.astral.sh/uv/) — `brew install uv` or `pip install uv`
- Android SDK platform-tools (`adb` on your PATH)
- A running Android emulator or a connected device
- **Optional — android-cli** (required for `get_layout`, `take_annotated_screenshot`, `resolve_coordinates`, and the `-lite` skills): see [Android CLI installation](https://developer.android.com/tools/agents/android-cli)

## Installation

### macOS — auto-start via launchctl

```sh
git clone https://github.com/vinicius-ssv/adb-interaction-mcp
cd adb-interaction-mcp
./install.sh
```

Registers the server as a LaunchAgent that starts on login and stays alive.

```
Logs:  ~/Library/Logs/adb-interaction-mcp/server.log
Stop:  launchctl unload ~/Library/LaunchAgents/com.adb-interaction-mcp.plist
Start: launchctl load  ~/Library/LaunchAgents/com.adb-interaction-mcp.plist
```

### Manual run (any platform)

```sh
uv run adb-mcp
```

## Claude Code configuration

Add the server to your project's `.mcp.json` (project-level) or `~/.claude/mcp.json` (global):

```json
{
  "mcpServers": {
    "android-adb": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["--directory", "/path/to/adb-interaction-mcp", "run", "adb-mcp"]
    }
  }
}
```

Replace `/path/to/adb-interaction-mcp` with the absolute path where you cloned the repo.

After adding, restart Claude Code (or run `claude mcp list` to verify it loaded).

## Available tools

All tools accept an optional `device` parameter (defaults to the single connected device).

### Device

| Tool | Description |
|------|-------------|
| `list_devices` | List all ADB-connected devices and emulators |
| `get_app_pid(package_name)` | Return PID if app is running, or "not running" |
| `current_activity` | Return the foreground package and activity name |

### Screen

| Tool | Description |
|------|-------------|
| `take_screenshot` | Capture the current screen as a PNG image |
| `dump_ui` | Dump the full UI hierarchy as XML (bounds, resource IDs, text, content-desc) |

### Input

| Tool | Description |
|------|-------------|
| `tap(x, y)` | Tap at screen coordinates |
| `long_press(x, y, duration_ms)` | Long-press at coordinates (default 1000 ms) |
| `swipe(x1, y1, x2, y2, duration_ms)` | Swipe gesture (default 300 ms) |
| `input_text(text)` | Type text into the focused field |
| `press_key(keycode)` | Press a key by name: `BACK`, `HOME`, `ENTER`, `DEL`, `TAB`, `SPACE`, `ESCAPE`, `DPAD_*`, `VOLUME_*`, `POWER`, etc. |

### Logs

| Tool | Description |
|------|-------------|
| `get_logcat(lines, package, level)` | Retrieve recent logcat output with optional package and level filters |
| `clear_logcat` | Clear the logcat buffer |

### App lifecycle

| Tool | Description |
|------|-------------|
| `launch_app(package_name)` | Launch an app by package name |
| `install_apk(apk_path)` | Install an APK from the host filesystem (replaces existing, supports test-only APKs) |
| `stop_app(package_name)` | Force-stop an app |
| `start_activity(activity)` | Start a specific activity by fully-qualified name (e.g. `com.example/.MainActivity`) |

### android-cli tools (token-efficient alternatives)

These three tools wrap [android-cli](https://developer.android.com/tools/agents/android-cli) and replace manual XML parsing and coordinate math. They are required by the `-lite` skills.

| Tool | Description |
|------|-------------|
| `get_layout(diff=False)` | Return the current UI as compact JSON. Pass `diff=True` to see only elements that changed since the last call — useful after a dropdown or modal opens. Prefer over `dump_ui` (JSON is smaller than XML). |
| `take_annotated_screenshot()` | Capture a screenshot with a numbered bounding box drawn around every detected UI element. Pair with `resolve_coordinates` — no coordinate math needed. |
| `resolve_coordinates(query)` | Resolve `#N` element labels from the last annotated screenshot to real `(x, y)` coordinates. Example: `resolve_coordinates("input tap #3")` → `"input tap 540 1200"`. Must call `take_annotated_screenshot` first. |

## Usage examples

Once configured, Claude Code can use these tools directly in conversation:

> "Take a screenshot of the emulator"
> "Dump the UI and find the Login button"
> "Tap at (540, 960) and then type hello@example.com"
> "Show me the last 50 logcat lines for com.example.app"
> "Install the APK at build/outputs/apk/debug/app-debug.apk"

## run-test skill — automated UI tests

The `run-test` Claude Code skill drives end-to-end UI tests against your Android app. Tests are plain markdown files with numbered steps in plain English — no code or selectors needed.

### Setup

1. **Copy the skill into your project:**

   ```sh
   cp .claude/commands/run-test.md  <your-project>/.claude/commands/run-test.md
   ```

2. **Write a test file** at `.claude/tests/<test-name>.md`:

   ```markdown
   1. Open the app
   2. Tap the Login button
   3. Enter email "user@example.com"
   4. Enter password "secret123"
   5. Tap Submit
   6. Wait for home screen
   ```

   See [`.claude/tests/example-flow.md`](.claude/tests/example-flow.md) for a complete template.

3. **Run the test** inside Claude Code:

   ```
   /run-test <test-name>
   ```

   Example: `/run-test login-flow`

### What the skill does

- Verifies a device is connected via `list_devices`
- Finds and reinstalls your app's debug APK (run `./gradlew assembleDebug` first if needed)
- Launches the app and executes each step
- Calls `dump_ui` once per screen to compute all coordinates before firing any interactions
- Takes screenshots only at `Wait` steps to confirm screen transitions
- Prints a final pass/fail summary table

### Internal performance rules

| Rule | Detail |
|------|--------|
| **Plan, then execute** | One `dump_ui` per screen; compute all coordinates before any taps |
| **Screenshots only at "Wait" steps** | Confirms new screen loaded; then immediately re-dumps |
| **Coordinate formula** | `x = (x1+x2)/2`, `y = (y1+y2)/2` from `bounds="[x1,y1][x2,y2]"` |
| **Keyboard dismissal** | Tap the next field directly — never `press_key BACK` (it navigates screens) |
| **Dropdowns** | Tap → re-dump → derive item coordinate → tap item |

## run-test-lite skill — token-efficient UI tests (requires android-cli)

`/run-test-lite` is a faster variant of `/run-test` that uses [android-cli](https://developer.android.com/tools/agents/android-cli) instead of raw ADB XML parsing.

### How it differs from /run-test

| Aspect | `/run-test` | `/run-test-lite` |
|--------|-------------|-----------------|
| UI layout | `dump_ui` → XML → manual bounds math | `take_annotated_screenshot` → numbered labels → `resolve_coordinates` |
| Coordinate extraction | Parse `bounds="[x1,y1][x2,y2]"` and average | `resolve_coordinates("input tap #N")` |
| Dropdown/modal updates | Full `dump_ui` re-dump | `get_layout(diff=True)` — only changed elements |
| Screen transition check | Separate `take_screenshot` | Re-uses `take_annotated_screenshot` (one call for both) |
| Prerequisite | ADB only | [android-cli](https://developer.android.com/tools/agents/android-cli) |

### Setup

1. **Copy the skill into your project:**

   ```sh
   cp .claude/commands/run-test-lite.md  <your-project>/.claude/commands/run-test-lite.md
   ```

2. **Install android-cli** — follow the [official guide](https://developer.android.com/tools/agents/android-cli) and make sure `android` is on your PATH.

3. **Write a test file** at `.claude/tests/<test-name>.md` (same format as `/run-test`).

4. **Run the skill** inside Claude Code:

   ```
   /run-test-lite <test-name>
   ```

   Example: `/run-test-lite login-flow`

### What the skill does

- Confirms a device is connected and installs/launches the debug APK
- On each new screen: calls `take_annotated_screenshot` once, resolves all element coordinates, fires all interactions
- After dropdowns/modals: calls `get_layout(diff=True)` — no full re-dump
- At `Wait` steps: calls `take_annotated_screenshot` to confirm navigation and label the next screen
- Prints a final pass/fail summary table (no per-step narration)

## generate-android-test skill — generate instrumented test classes

The `generate-android-test` Claude Code skill generates a full Compose UI instrumented test from a plain-English markdown spec. It inspects your source composables, adds missing `testTag` modifiers, optionally walks the live app via ADB, and outputs a Page Object Model test class ready to run.

### Setup

1. **Copy the skill into your project:**

   ```sh
   cp .claude/commands/generate-android-test.md  <your-project>/.claude/commands/generate-android-test.md
   ```

2. **Write a test spec** at `.claude/tests/<test-name>.md`:

   ```markdown
   1. Open the app
   2. Enter "user@example.com" in the email field
   3. Enter "secret123" in the password field
   4. Tap the Login button
   5. Wait for home screen
   6. Verify welcome message is visible
   ```

3. **Run the skill** inside Claude Code:

   ```
   /generate-android-test <test-name>
   ```

   Example: `/generate-android-test login-flow`

### What the skill does

| Step | Action |
|------|--------|
| 1 | Reads the markdown test spec |
| 2 | Detects existing test patterns in `androidTest/` and follows them |
| 3 | Adds missing Compose UI test dependencies to `build.gradle.kts` |
| 4 | Inspects source composables and adds `testTag` modifiers to interactive elements |
| 5 | Optionally walks the live app via ADB to confirm real selectors (skips gracefully if no device) |
| 6 | Generates screen helper classes (Page Object Model) and the test class |
| 7 | Reports all created/modified files and how to run |

### Output structure

```
<app-module>/src/androidTest/kotlin/<package>/
  screens/
    <ScreenName>Screen.kt    ← one file per distinct screen in the flow
  <TestName>Test.kt          ← the test class
```

### testTag naming convention

Tags use `snake_case` prefixed with the screen name:

```
login_username_field
login_submit_button
home_filter_dropdown
settings_theme_switch
```

### Running the generated tests

```sh
# All instrumented tests
./gradlew connectedAndroidTest

# Single test class
./gradlew connectedAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.app.LoginFlowTest
```

Or right-click the test class in Android Studio and select **Run**.

## generate-android-test-lite skill — instrumented tests via android-cli (requires android-cli)

`/generate-android-test-lite` is a faster variant of `/generate-android-test`. Steps 1–4 and 6–7 are identical; only the live-device navigation in Step 5 differs.

### How it differs from /generate-android-test

| Aspect | `/generate-android-test` | `/generate-android-test-lite` |
|--------|--------------------------|-------------------------------|
| Live UI inspection | `dump_ui` → XML → manual bounds math | `take_annotated_screenshot` → numbered labels → `resolve_coordinates` |
| Dropdown element discovery | Full `dump_ui` re-dump | `get_layout(diff=True)` — only changed elements |
| Screen transition confirmation | Separate `take_screenshot` | Re-uses `take_annotated_screenshot` (one call for both) |
| Prerequisite | ADB only (device optional) | [android-cli](https://developer.android.com/tools/agents/android-cli) (device optional) |

When no device is connected, both skills skip Step 5 and generate best-effort code from the `testTag` map built in Step 4.

### Setup

1. **Copy the skill into your project:**

   ```sh
   cp .claude/commands/generate-android-test-lite.md  <your-project>/.claude/commands/generate-android-test-lite.md
   ```

2. **Install android-cli** — follow the [official guide](https://developer.android.com/tools/agents/android-cli) and make sure `android` is on your PATH.

3. **Write a test spec** at `.claude/tests/<test-name>.md` (same format as `/generate-android-test`).

4. **Run the skill** inside Claude Code:

   ```
   /generate-android-test-lite <test-name>
   ```

   Example: `/generate-android-test-lite login-flow`

The output structure, `testTag` naming convention, and how to run the generated tests are the same as for `/generate-android-test` — see that section above.

## Choosing between the standard and lite variants

| Situation | Recommended skill |
|-----------|-------------------|
| android-cli not installed | `/run-test`, `/generate-android-test` |
| android-cli installed, long flows with many screens | `/run-test-lite`, `/generate-android-test-lite` |
| Debugging a single step interactively | `/run-test` (XML output is easier to inspect manually) |
| CI / automated script | either — both produce the same final artefacts |

## Project structure

```
server.py             MCP server (FastMCP, port 8755, stdio transport)
pyproject.toml        Python project config and dependencies
install.sh            macOS launchctl setup script
uv.lock               Locked dependency versions
.gitignore
.claude/
  commands/
    run-test.md                    Claude Code skill — drives live ADB UI tests (ADB-only)
    run-test-lite.md               Claude Code skill — same as run-test, uses android-cli
    generate-android-test.md       Claude Code skill — generates instrumented test classes (ADB-only)
    generate-android-test-lite.md  Claude Code skill — same as generate-android-test, uses android-cli
  tests/
    example-flow.md   Example test file template
```
