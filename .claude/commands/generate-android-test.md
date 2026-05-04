Generate a Compose UI instrumented test class from a `.claude/tests/` markdown file.
Tests follow the Page Object Model and run via `./gradlew connectedAndroidTest`.

## Usage
`/generate-android-test <test-name>` — e.g. `/generate-android-test email-sign-up-flow`

## Instructions

### Step 1 — Read the test specification
Read `.claude/tests/$ARGUMENTS.md`. If the file does not exist, list the available files in `.claude/tests/` and stop.

### Step 2 — Check for existing test patterns
```
find <app-module>/src/androidTest -name "*.kt" 2>/dev/null
```
where `<app-module>` is the module that contains the Android application (e.g. `composeApp`, `app`).

If files exist, read them to understand the package structure, base classes, helper conventions, and import style. Follow those patterns instead of the defaults below.

### Step 3 — Add test dependencies if missing
Read the app module's `build.gradle.kts`.

If `compose.uiTest` is absent from `androidInstrumentedTest.dependencies`, apply both of the following edits:

**A. Inside `kotlin { sourceSets { } }`** — add a new source set block.
`compose.uiTest` provides assertions only. `ui-test-junit4` provides `createAndroidComposeRule`/`createComposeRule` — it must be added explicitly with the version that CMP resolves `androidx.compose.ui:ui-test` to (check `./gradlew :app:dependencies` or the Gradle cache).
For CMP 1.9.3 the correct version is `1.9.4`.

First, add the version and library to `gradle/libs.versions.toml`:
```toml
[versions]
androidx-compose-ui-test = "1.9.4"   # match CMP's resolved androidx.compose.ui:ui-test version

[libraries]
androidx-compose-ui-test-junit4 = { module = "androidx.compose.ui:ui-test-junit4", version.ref = "androidx-compose-ui-test" }
```

Then add to `build.gradle.kts` inside `kotlin { sourceSets { } }`:
```kotlin
@OptIn(org.jetbrains.compose.ExperimentalComposeLibrary::class)
androidInstrumentedTest.dependencies {
    implementation(libs.androidx.testExt.junit)
    implementation(compose.uiTest)
    implementation(libs.androidx.compose.ui.test.junit4)
}
```

**B. Inside `android { defaultConfig { } }`** — add:
```kotlin
testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
```

Notes:
- `compose.uiTest` is the CMP multiplatform assertions API — it does **not** include the JUnit4 rule.
- `ui-test-junit4` provides `createAndroidComposeRule<Activity>()` and `createComposeRule()`.
- `compose.uiTestManifest` does **not** exist in CMP 1.x's plugin DSL — do not add it.

### Step 4 — Inspect source composables and add missing testTags

For each distinct screen in the test flow, find its Kotlin source file(s) under
`<app-module>/src/commonMain` and `<app-module>/src/androidMain` by searching for
composable names or screen-related keywords derived from the test spec steps.

#### 4.1 — Identify interactive elements

Read each screen's composable file(s) and list every interactive element:
`TextField`, `OutlinedTextField`, `Button`, `IconButton`, `RadioButton`,
`Checkbox`, `Switch`, `DropdownMenu`/`DropdownMenuItem`, and any custom
components that wrap these.

#### 4.2 — Decide whether a testTag is needed

**Default rule: always add a testTag.** `onNodeWithTag` is the preferred selector
for every interactive element (buttons, text fields, checkboxes, dropdowns,
screen-landmark containers). `onNodeWithText` is a fallback of last resort.

A testTag is **required** for:
- All buttons and CTAs (even those with unique text — text changes break tests)
- All input fields
- All checkboxes, radio buttons, switches
- Dropdown triggers
- Screen-landmark containers used in `assertVisible()` checks
- Icon-only buttons (no text, no content description)

`onNodeWithText` is acceptable **only** for:
- Dynamic list items inside a scrollable dialog/sheet whose content is
  data-driven (e.g. a picker from a remote list) — tagging every item
  is impractical; scroll to the item first with `performScrollToNode(hasText(…))`
  then tap with `onNodeWithText(…)`
- Inline display-only text that is being asserted as visible (not interacted with)

#### 4.3 — Add testTags to source files

For each element that needs a tag:

**Inline element** (tag applied at the call site):
```kotlin
// Before
Button(onClick = { … }) { Text("Next") }

// After
Button(onClick = { … }, modifier = Modifier.testTag("login_next_button")) { Text("Next") }
```

**Reusable component without a `modifier` param** — add the param rather than
hard-coding the tag, so every call site can pass its own tag:
```kotlin
// Before
@Composable
fun InputField(label: String, value: String, onValueChange: (String) -> Unit) { … }

// After
@Composable
fun InputField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,   // ← added
) {
    TextField(value = value, onValueChange = onValueChange, modifier = modifier, …)
}
```
Then update every call site that needs a tag:
```kotlin
InputField(label = "Username", …, modifier = Modifier.testTag("login_username_field"))
```

**Naming convention** — use `snake_case`, prefixed with the screen name:
`login_username_field`, `settings_theme_dropdown`, `profile_interests_list`.

#### 4.4 — Record the tag map

After editing source files, record the complete tag map:
```
Screen          Element                   testTag
──────────────────────────────────────────────────────
Login           username TextField         login_username_field
Login           password TextField         login_password_field
Login           submit Button              login_submit_button
Home            filter Dropdown            home_filter_dropdown
…
```
Use this map in Step 6 when choosing selectors.

### Step 5 — Navigate the app to collect real element data

This step requires a connected device and a built debug APK. If either is unavailable, skip to Step 6 and generate best-effort code using the tag map from Step 4 and text inferred from the markdown steps.

#### 5.1 — Setup

1. `mcp__android-adb__list_devices` — confirm a device is connected.
2. Find the APK: `find . -name "*.apk" -path "*/debug/*" | head -1`
3. Install with `mcp__android-adb__install_apk`, launch with `mcp__android-adb__launch_app`.

#### 5.2 — Plan-then-execute (one dump per screen)

When you arrive at a new screen:
1. Call `mcp__android-adb__dump_ui` **once**.
2. From that single XML, compute **all** center coordinates you will need on that screen: `x = (x1+x2)/2`, `y = (y1+y2)/2`.
3. **Then** fire all taps and inputs back-to-back — no intermediate dumps or screenshots.

The only exceptions that require a re-dump are:
- A **dropdown or modal opened** (new nodes appeared).
- A test step says **"Wait"** (you navigated to the next screen).

#### 5.3 — Screenshots

Only call `mcp__android-adb__take_screenshot` when a step says "Wait", to confirm the new screen loaded. Do **not** take screenshots between individual taps or text inputs.

#### 5.4 — Keyboard dismissal

**Never use `press_key BACK` to dismiss the keyboard** if the app uses BACK for screen navigation — pressing BACK would navigate away instead of closing the keyboard. To dismiss the keyboard before tapping a non-field element (e.g. a button), tap a non-interactive area or a fixed header element. Verify the app's BACK behavior before using it.

#### 5.5 — Dropdowns

Tap the dropdown trigger → re-dump (layout changed) → derive item coordinate → tap item. Do **not** re-dump after selecting the item.

#### 5.6 — Selector map

For each screen, record: `{ step description → (selectorFn, selectorValue) }`.

Selector priority (use the first that applies):
1. `testTag` set in Step 4 → `onNodeWithTag("tag_name")` — **always preferred**
2. `resource-id` present in dump (and no testTag was added) → `onNodeWithTag(id.substringAfterLast('/'))`
3. Dynamic list items inside a scrollable dialog with no practical tagging → scroll with `performScrollToNode(hasText(…))` then `onNodeWithText(…)`

**Never use** `onNodeWithText` for buttons, fields, or landmark checks — those must have testTags.
**Never use** `onAllNodes(hasSetTextAction())[index]` — add a testTag to the field instead.

### Step 6 — Generate the test files

**Resolve the package name and output path first.**
Read the app module's `build.gradle.kts` (or `build.gradle`) and extract the `namespace` (or `applicationId`) value from the `android { }` block.
Convert it to a directory path: `com.example.app` → `com/example/app`.

**Root output directory:** `<app-module>/src/androidTest/kotlin/<package-path>/`
where `<app-module>` is the module that contains the Android application (e.g. `composeApp`, `app`).

Convert the test name from kebab-case to PascalCase:
`email-sign-up-flow` → `EmailSignUpFlow`

#### Output structure

```
<app-module>/src/androidTest/kotlin/<package-path>/
  screens/
    <ScreenName>Screen.kt    ← one file per distinct screen in the flow
  <TestName>Test.kt          ← the test class
```

#### Screen helper template

Each screen class encapsulates all interactions for that screen. Methods are named after _intent_, not after UI implementation.

```kotlin
package <package>.screens

import androidx.compose.ui.test.ComposeTestRule
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput

class <ScreenName>Screen(private val rule: ComposeTestRule) {

    // Assertion — call this at the start of a screen block to confirm navigation succeeded
    fun assertVisible() =
        rule.onNodeWithTag("<screen_landmark_tag>").assertIsDisplayed()

    // Example tap action
    fun tap<ActionName>() =
        rule.onNodeWithTag("<button_tag>").performClick()

    // Example text field action — clicks to focus, then types
    fun enter<FieldName>(value: String) {
        rule.onNodeWithTag("<field_tag>").performClick()
        rule.onNodeWithTag("<field_tag>").performTextInput(value)
    }

    // Example dropdown — expand then select
    fun select<OptionName>(option: String) {
        rule.onNodeWithTag("<dropdown_tag>").performClick()
        rule.onNodeWithText(option).performClick()
    }
}
```

#### Test class template

```kotlin
package <package>

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import <package>.screens.<ScreenName>Screen
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class <TestName>Test {

    @get:Rule
    val composeTestRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun <camelCaseTestName>() {
        <ScreenName>Screen(composeTestRule).apply {
            assertVisible()
            // one method call per test step
        }

        <NextScreenName>Screen(composeTestRule).apply {
            assertVisible()
            // ...
        }
    }
}
```

#### Step → code translation table

| Markdown step pattern | Generated Compose UI Test code |
|---|---|
| "Open the app" / "Launch the app" | `// app starts automatically via composeTestRule` |
| "Tap/Click the X button" | `screen.tapX()` → `onNodeWithTag("x_button").performClick()` |
| "Enter X in the Y field" | `screen.enterY("X")` → `onNodeWithTag("y_field").performTextInput("X")` |
| "Select X from dropdown/list" | `screen.selectX()` → click trigger tag + click item text |
| "Wait for X screen" | `screen.assertVisible()` at the top of the next screen block |
| "Verify X is visible" | `rule.onNodeWithTag("x_tag").assertIsDisplayed()` |
| "Select all / toggle all options" | `onAllNodesWithTag("…").onEach { it.performClick() }` |

#### Waiting between screens
After a navigation action, Compose UI Test auto-waits for a short period. If a step needs an explicit wait, use:
```kotlin
composeTestRule.waitUntil(timeoutMillis = 5_000) {
    composeTestRule.onAllNodesWithTag("<next_screen_landmark_tag>").fetchSemanticsNodes().isNotEmpty()
}
```

### Step 7 — Report output

Print:
- Source files edited to add `testTag` (if any), with a summary of what was tagged
- Test files created (full relative paths)
- `build.gradle.kts` changes applied (if any)
- How to run:
  - From terminal: `./gradlew connectedAndroidTest`
  - From Android Studio: right-click the test class → Run
