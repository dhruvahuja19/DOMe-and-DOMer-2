# Utils Directory

This directory contains utility functions and helper modules used throughout the benchmark system.

## Files

### `accessibility_utils.py`
- Handles accessibility tree extraction and HTML element comparison
- Key functions:
  - `get_accessibility_tree()`: Extracts accessibility tree from webpage
  - `get_element_html_context()`: Gets HTML context for an element
  - `compare_html_elements()`: Compares two HTML elements for similarity

### Other Utils
- Helper functions for web interaction
- Image processing utilities
- Common data structures and types

## HTML Element Comparison

The HTML comparison system uses three metrics:
1. **Structure Score (40%)**
   - Tag name matching
   - Parent element matching
   - Sibling context

2. **Attributes Score (30%)**
   - Matching of key attributes (id, class, etc.)
   - Handling of dynamic attributes

3. **Content Score (30%)**
   - Inner HTML similarity
   - Text content matching

## Usage Example

```python
from utils.accessibility_utils import get_element_html_context, compare_html_elements

# Get HTML context for an element
element_context = get_element_html_context(driver, element)

# Compare with ground truth
similarity_score = compare_html_elements(
    element_context,
    ground_truth_html
)

# Score breakdown
print(f"Structure Score: {similarity_score['structure_score']}")
print(f"Attributes Score: {similarity_score['attributes_score']}")
print(f"Content Score: {similarity_score['content_score']}")
print(f"Total Score: {similarity_score['total_score']}")
```
