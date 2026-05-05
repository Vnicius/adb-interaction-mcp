Run an ADB MCP interaction test from `.claude/tests/` using android-cli for token-efficient UI navigation.

## Usage
`/run-test-lite <test-name>` — e.g. `/run-test-lite email-sign-up-flow`

## How this differs from /run-test
- `take_annotated_screenshot` + `resolve_coordinates` replace manual coordinate calculation from XML bounds
- `get_layout(diff=True)` replaces full re-dumps after dropdowns/modals
- `take_annotated_screenshot` doubles as screen-transition confirmation, eliminating separate screenshot calls

## Instructions

1. Read the test file at `.claude/tests/$ARGUMENTS.md`. If the file does not exist, list available files in `.claude/tests/` and ask the user to pick one.

2. Use `mcp__android-adb__list_devices` to confirm a device is connected. If none found, stop.

3. Reinstall and launch the app:
   - Run `find . -name "*.apk" -path "*/debug/*" | head -1` via Bash to locate the debug APK. If nothing is returned, stop and tell the user to build the project first (e.g. `./gradlew assembleDebug`).
   - Use `mcp__android-adb__install_apk` with the APK path found above.
   - Determine the package name: `aapt dump badging <apk-path> 2>/dev/null | grep "^package" | sed "s/.*name='\([^']*\)'.*/\1/"`. Fall back to: `grep -r "applicationId" . --include="*.gradle.kts" --include="*.gradle" | head -1`.
   - Use `mcp__android-adb__launch_app` with the detected package name.

4. Process test steps with these rules:

   ### Arriving at a new screen — annotate once, resolve all

   When you arrive at a new screen:
   1. Call `mcp__android-adb__take_annotated_screenshot` **once** — every UI element is numbered.
   2. Identify the label numbers for **every interaction you need on that screen**.
   3. For each interaction, call `mcp__android-adb__resolve_coordinates("input tap #N")` to get exact `(x, y)`.
   4. Fire all taps and inputs back-to-back — no intermediate screenshots or layout calls.

   Do **not** re-annotate mid-screen unless a dropdown/modal opened.

   ### Re-checks after dropdowns/modals

   After a dropdown opens or a modal appears:
   1. Call `mcp__android-adb__get_layout(diff=True)` to see only the new elements.
   2. Resolve or compute coordinates for the target item only.
   3. Tap the item. Do **not** re-check after selection.

   ### Screen transitions ("Wait" steps)

   At a "Wait" step, call `mcp__android-adb__take_annotated_screenshot` — this confirms the new screen loaded **and** gives element labels for the next phase. No separate screenshot needed.

   ### Typing

   Tap the target field using resolved coordinates, then call `mcp__android-adb__input_text`.

   **Never use `press_key BACK` to dismiss the keyboard** — in most apps BACK navigates screens. Tap a non-interactive element in a fixed header instead.

   ### Fallback when annotation misses an element

   If a needed element is not annotated (e.g. a custom canvas), call `mcp__android-adb__get_layout` and compute `x = (x1+x2)/2`, `y = (y1+y2)/2` from the JSON bounds.

5. If a step fails, call `mcp__android-adb__take_annotated_screenshot`, describe what was on screen, and stop.

6. Print a final summary table only — no per-step narration while running:

| Step | Result |
|------|--------|
| Open the app | ✓ |
| ... | ... |
