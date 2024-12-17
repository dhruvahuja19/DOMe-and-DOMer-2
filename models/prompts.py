"""Specialized prompts for different web interaction scenarios."""

CLICK_PROMPT = """Analyze the following click interaction task:
Task: {task}
Element: {element}

Consider:
1. Is this a simple click or does it require special handling (e.g., double-click, right-click)?
2. Are there any potential timing issues (e.g., waiting for element to be clickable)?
3. Should we verify any state changes after the click?

Generate a JSON interaction specification."""

TYPE_PROMPT = """Analyze the following text input task:
Task: {task}
Element: {element}
Text to Input: {input_text}

Consider:
1. Should we clear existing text first?
2. Are there any special characters that need handling?
3. Should we simulate natural typing speed?
4. Do we need to trigger any events after typing (e.g., Enter key)?

Generate a JSON interaction specification."""

HOVER_PROMPT = """Analyze the following hover interaction task:
Task: {task}
Element: {element}

Consider:
1. How long should the hover last?
2. Are there any tooltip or dropdown menus that need time to appear?
3. Should we verify the hover state visually?

Generate a JSON interaction specification."""

NAVIGATION_PROMPT = """Analyze the following navigation task:
Task: {task}
Element: {element}

Consider:
1. Should we wait for any redirects?
2. Are there any confirmation dialogs?
3. Should we verify the new URL?

Generate a JSON interaction specification."""

ERROR_ANALYSIS_PROMPT = """Analyze the following error:
Task: {task}
Error: {error}
Previous Attempts: {attempts}

Consider:
1. Is this a timing issue?
2. Is the element actually present but not visible/clickable?
3. Has the page structure changed?
4. Are we using the right selector?

Suggest a modified interaction or respond with "GIVE UP" if unrecoverable."""

VALIDATION_PROMPT = """Validate the following interaction result:
Task: {task}
Element Before: {before_html}
Element After: {after_html}
Screenshots: {screenshots}

Consider:
1. Did the element state change as expected?
2. Are there any visible changes in the screenshots?
3. Did any errors occur?
4. Is the result consistent with the task goal?

Respond with exactly 'YES' or 'NO'."""
