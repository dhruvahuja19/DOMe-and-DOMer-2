# DOM Task Format

This document describes the format for DOM interaction tasks in our benchmark.

## Schema

Tasks are defined in JSONL format, where each line is a valid JSON object following the schema in `task_schema.json`.

## Example Task

```json
{
    "web_name": "Cambridge Dictionary",
    "id": "cambridge_lookup_1",
    "task": "Click the search box and type 'hello'",
    "web": "https://dictionary.cambridge.org/",
    "element_type": "input",
    "interaction": "type",
    "target_element": {
        "type": "id",
        "value": "searchword"
    },
    "input_text": "hello",
    "target_html": "<input type=\"text\" id=\"searchword\" class=\"search-input\" ...>",
    "ground_truth": {
        "screenshot": "cambridge_lookup_1_gt.png",
        "description": "The word 'hello' has been entered in the search box",
        "visual_changes": [
            "Text 'hello' appears in search box",
            "Text cursor visible at end of input",
            "Search suggestions may appear"
        ],
        "success_criteria": [
            "Input text matches 'hello' exactly",
            "Text is visible in search box",
            "Search box maintains focus"
        ]
    }
}
```

## Field Descriptions

### Basic Information
- `web_name`: Name of the website
- `id`: Unique identifier for the task
- `task`: Human-readable task description
- `web`: Website URL

### Element and Interaction
- `element_type`: Type of HTML element (input, button, link, etc.)
- `interaction`: Type of interaction (click, type, hover)
- `target_element`: How to find the element
  - `type`: Selector type (id, class, text)
  - `value`: Selector value
- `input_text`: Text to type (only for type interactions)

### Validation
- `target_html`: The actual HTML element for structural validation
- `ground_truth`: Validation data
  - `screenshot`: Reference screenshot filename
  - `description`: What should happen
  - `visual_changes`: List of expected visual changes
  - `success_criteria`: Specific conditions for success

## Validation Process

Tasks are validated using two methods:
1. **Visual Validation** (60% of score)
   - Compares screenshots before/after interaction
   - Verifies visual changes match ground truth
   
2. **HTML Validation** (40% of score)
   - Matches the HTML element the model interacted with
   - Checks structure, attributes, and content

## Adding New Tasks

1. Follow the schema in `task_schema.json`
2. Ensure unique task IDs
3. Provide clear success criteria
4. Include reference screenshots
5. Fill in the `target_html` field with the actual HTML element
