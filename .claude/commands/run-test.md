Run an ADB MCP interaction test from `.claude/tests/`.

## Usage
`/run-test <test-name>` — e.g. `/run-test email-sign-up-flow`

## Instructions

1. Read the test file at `.claude/tests/$ARGUMENTS.md`. If the file does not exist, list available files in `.claude/tests/` and ask the user to pick one.

2. Use `mcp__android-adb__list_devices` to confirm a device is connected. If none found, stop.

3. Reinstall and launch the app:
   - Run `find . -name "*.apk" -path "*/debug/*" | head -1` via Bash to locate the debug APK. If nothing is returned, stop and tell the user to build the project first (e.g. `./gradlew assembleDebug`).
   - Use `mcp__android-adb__install_apk` with the `apk_path` set to the path found above to reinstall it.
   - Determine the package name by running `aapt dump badging <apk-path> 2>/dev/null | grep "^package" | sed "s/.*name='\([^']*\)'.*/\1/"`. If `aapt` is not available, fall back to: `grep -r "applicationId" . --include="*.gradle.kts" --include="*.gradle" | head -1`.
   - Use `mcp__android-adb__launch_app` with the detected package name to open the app.

4. Process the test steps with these performance rules:

   ### Plan, then execute — no mid-screen re-dumps

   When you arrive at a new screen, call `mcp__android-adb__dump_ui` **once**. From that single dump, compute the center coordinates for **every interaction you will need on that screen** before issuing any tool call. Then fire all taps and inputs back-to-back with no intermediate dumps or screenshots. The only exceptions that require a re-dump are:
   - A **dropdown/modal opened** (new nodes appeared on screen).
   - A step explicitly says **"Wait"** (navigate to next screen).

   ### Screenshots — only at "Wait" steps

   Only call `mcp__android-adb__take_screenshot` when the test step says "Wait". Use it solely to confirm the new screen loaded, then immediately call `dump_ui` for that screen and discard the screenshot.

   ### Coordinate calculation

   Center of a node with `bounds="[x1,y1][x2,y2]"`: `x = (x1+x2)/2`, `y = (y1+y2)/2`. Use `mcp__android-adb__tap`.

   ### Typing and keyboard dismissal

   Tap the target field, then call `mcp__android-adb__input_text`. To move to the next field, tap it directly — the keyboard dismisses implicitly.

   **Never use `press_key BACK` to dismiss the keyboard.** In most apps, BACK navigates back through screens (or exits to the Android home screen) instead of closing the keyboard. If the keyboard would obscure a non-field tap target (e.g. a button at the bottom), tap a non-interactive element in a fixed header area.

   ### Dropdowns

   Tap the dropdown → re-dump (layout changed) → derive item coordinate → tap item. Do **not** re-dump after selecting the item; return to the pre-planned flow.

5. If a step fails, take one screenshot, describe what was on screen, and stop.

6. Print a final summary table only — no per-step narration while running:

| Step | Result |
|------|--------|
| Open the app | ✓ |
| ... | ... |
