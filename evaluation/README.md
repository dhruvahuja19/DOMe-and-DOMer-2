# DOM and DOMer-2 Evaluation

This directory contains the evaluation tools for the DOM and DOMer-2 benchmark.

## Overview

The evaluation system combines two approaches:
1. Visual Validation (60% of score): Using GPT-4V to analyze screenshots
2. HTML Element Validation (40% of score): Comparing actual HTML elements

## Usage

```bash
python auto_eval.py \
    --tasks ../data/dom_tasks.jsonl \
    --results ../results/run_001 \
    --output ../results/run_001/evaluation.json \
    --openai-key YOUR_API_KEY
```

## Evaluation Process

1. **Visual Validation (60%)**
   - Compare before/after screenshots
   - Verify visual changes match expected interaction
   - Check element visibility and state changes
   - Uses GPT-4V for intelligent visual comparison

2. **HTML Element Validation (40%)**
   - Compare model's selected HTML element with ground truth
   - Structure score (40%): Tag hierarchy and relationships
   - Attributes score (30%): Element properties and identifiers
   - Content score (30%): Inner HTML and text content

3. **Success Criteria**
   - Visual score ≥ 0.9 for visual validation
   - HTML similarity score ≥ 0.9 for element validation
   - Combined weighted score ≥ 0.9 for overall success

## Output Format

```json
{
    "total_tasks": 10,
    "successful_tasks": 8,
    "evaluations": [
        {
            "task_id": "task_001",
            "visual_evaluation": {
                "score": 0.95,
                "details": "Detailed visual evaluation..."
            },
            "html_evaluation": {
                "score": 0.92,
                "structure_score": 0.95,
                "attributes_score": 0.90,
                "content_score": 0.89
            },
            "final_score": 0.94,
            "success": true,
            "timestamp": 1234567890
        }
    ]
}
```

## Scoring Details

### Visual Score (60%)
- Element visibility and positioning
- State changes (hover effects, expansions)
- Content updates and transitions
- Overall visual accuracy

### HTML Score (40%)
1. **Structure (40% of HTML score)**
   - Correct tag name
   - Parent-child relationships
   - Sibling context

2. **Attributes (30% of HTML score)**
   - ID and class matching
   - ARIA attributes
   - Event handlers
   - Custom data attributes

3. **Content (30% of HTML score)**
   - Inner HTML similarity
   - Text content matching
   - Nested element structure

## Requirements

- OpenAI API key with GPT-4V access
- Python 3.8+
- Required packages in `requirements.txt`
