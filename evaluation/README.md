# DOM and DOMer-2 Evaluation

This directory contains the evaluation tools for the DOM and DOMer-2 benchmark.

## Overview

The evaluation system combines two approaches:
1. Visual Validation (60% of score): Using GPT-4V to analyze screenshots
2. HTML Element Validation (40% of score): Comparing actual HTML elements

## Directory Structure

```
evaluation/
├── ground_truth/        # Ground truth screenshots
│   └── task_1_gt.png   # Named consistently as task_{id}_gt.png
├── auto_eval.py        # Main evaluation script
├── image_match.py      # GPT-4V based image comparison
└── fuzzy_match.py      # HTML element comparison
```

## HTML Element Validation

The system compares the HTML element that was actually interacted with against the expected element defined in the task:

1. **Expected HTML**: Defined in task file under `target_html`
   ```json
   {
     "target_html": "<input id='searchword' type='text' ...>"
   }
   ```

2. **Actual HTML**: Captured during interaction using `element.get_attribute('outerHTML')`
   - Stored in results as `html_element`
   - Includes all runtime attributes and state

3. **Comparison Criteria**:
   - Element type (tag name)
   - Key attributes (id, class, etc.)
   - Content and inner HTML
   - Role and accessibility attributes

4. **Fuzzy Matching**:
   - Uses GPT-4 to understand semantic equivalence
   - Tolerates dynamic/runtime attributes
   - Focuses on functional equivalence

## Visual Validation

Uses GPT-4V to compare:
1. Ground truth screenshot
2. Actual screenshot after interaction

## Running Evaluation

The evaluation is typically run through the main benchmark script:
```bash
python ../run.py --tasks data/tasks.jsonl --output data/results --evaluate
```

Or can be run separately:
```bash
python auto_eval.py \
    --tasks-file data/tasks.jsonl \
    --results-dir data/results.json \
    --output-file data/evaluation.json
```

## Output Format

```json
{
  "total_tasks": 10,
  "successful_tasks": 8,
  "evaluations": [
    {
      "task_id": 1,
      "success": true,
      "visual_score": 0.95,
      "html_score": 1.0,
      "final_score": 0.97,
      "visual_reasoning": "The search box contains 'hello' as expected...",
      "html_reasoning": "The input element matches with correct id and attributes..."
    }
  ]
}
```
