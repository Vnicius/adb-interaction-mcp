Generate a Compose UI instrumented test class from a `.claude/tests/` markdown file.
Tests follow the Page Object Model and run via `./gradlew connectedAndroidTest`.

## Usage
`/generate-android-test <test-name>` — e.g. `/generate-android-test email-sign-up-flow`

## Instructions

### Step 1 — Read the test specification
Read `.claude/tests/$ARGUMENTS.md`. If the file does not exist, list the available files in `.claude/tests/` and stop.

### Step 2 — Check for existing test patterns
```
find composeApp/src/androidTest -name "*.kt" 2>/dev/null
```
If files exist, read them to understand the package structure, base classes, helper conventions, and import style. Follow those patterns instead of the defaults below.

### Step 3 — Add test dependencies if missing
Read `composeApp/build.gradle.kts`.

If `compose.uiTest` is absent from `androidInstrumentedTest.dependencies`, apply both of the following edits:

**A. Inside `kotlin { sourceSets { } }`** — add a new source set block (the `@OptIn` is required because `compose.uiTest` is an experimental CMP API):
```kotlin
@OptIn(org.jetbrains.compose.ExperimentalComposeLibrary::class)
androidInstrumentedTest.dependencies {
    implementation(libs.androidx.testExt.junit)
    implementation(compose.uiTest)
}
```

**B. Inside `android { defaultConfig { } }`** — add:
```kotlin
testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
```

Note: `compose.uiTestManifest` does **not** exist in CMP 1.x's plugin DSL — do not add it. The app's existing `MainActivity` registration in the manifest is sufficient.

### Step 4 — Navigate the app to collect real element data

This step requires a connected device and a built debug APK. If either is unavailable, skip to Step 5 and generate best-effort code using text inferred from the markdown steps.

1. `mcp__android-adb__list_devices` — confirm a device is connected.
2. Find and install the APK:
   ```
   find . -name "*.apk" -path "*/debug/*" | head -1
   ```
   Install with `mcp__android-adb__install_apk`, then launch with `mcp__android-adb__launch_app`.
3. Walk through the test steps. For each distinct screen:
   a. Navigate there using the ADB interaction tools, following the test steps exactly.
   b. Call `mcp__android-adb__dump_ui` **once** per screen. From the XML, build a selector map for every element the test will touch.
   c. Selector priority (first non-empty wins):
      - `resource-id` present → `onNodeWithTag(id.substringAfterLast('/'))`
      - `content-desc` present → `onNodeWithContentDescription("...")`
      - `text` present → `onNodeWithText("...")`
      - Text input fields (`class="android.widget.EditText"`) → match by surrounding label or hint `text`
4. Record the selector map per screen: `{ step description → (selectorFn, value) }`

### Step 5 — Generate the test files

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
        rule.onNodeWithText("<unique title or landmark text>").assertIsDisplayed()

    // Example tap action
    fun tap<ActionName>() =
        rule.onNodeWithText("<button text>").performClick()

    // Example text field action — clicks to focus, then types
    fun enter<FieldName>(value: String) {
        rule.onNodeWithText("<field label or placeholder>").performClick()
        rule.onNodeWithText("<field label or placeholder>").performTextInput(value)
    }

    // Example dropdown — expand then select
    fun select<OptionName>() {
        rule.onNodeWithText("<dropdown label>").performClick()
        rule.onNodeWithText("<option text>").performClick()
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
| "Tap/Click the X button" | `screen.tapX()` → `onNodeWithText("X").performClick()` |
| "Enter X in the Y field" | `screen.enterY("X")` → `onNodeWithText("Y").performTextInput("X")` |
| "Select X from dropdown/list" | `screen.selectX()` → click header + click item |
| "Wait for X screen" | `screen.assertVisible()` at the top of the next screen block |
| "Verify X is visible" | `rule.onNodeWithText("X").assertIsDisplayed()` |
| "Select all / toggle all options" | `onAllNodesWithTag("…").onEach { it.performClick() }` |

#### Waiting between screens
After a navigation action, Compose UI Test auto-waits for a short period. If a step needs an explicit wait, use:
```kotlin
composeTestRule.waitUntil(timeoutMillis = 5_000) {
    composeTestRule.onAllNodesWithText("<next screen landmark>").fetchSemanticsNodes().isNotEmpty()
}
```

### Step 6 — Report output

Print:
- Files created (full relative paths)
- `build.gradle.kts` changes applied (if any)
- How to run:
  - From terminal: `./gradlew connectedAndroidTest`
  - From Android Studio: right-click the test class → Run
