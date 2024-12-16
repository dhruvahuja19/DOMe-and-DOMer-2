# DOM and DOMer-2 Evaluation

This directory contains the evaluation tools for the DOM and DOMer-2 benchmark.

## Overview

The evaluation uses GPT-4V to assess web interactions by analyzing:
1. Before/After screenshots of the webpage
2. Accessibility tree information
3. Task descriptions and expected outcomes

## Usage

```bash
python auto_eval.py \
    --tasks ../data/dom_tasks.jsonl \
    --results ../results/run_001 \
    --output ../results/run_001/evaluation.json \
    --openai-key YOUR_API_KEY
```

## Evaluation Process

1. **Screenshot Analysis**
   - Compare before/after states
   - Verify visual changes match expected interaction
   - Check element visibility and state changes

2. **Accessibility Tree Verification**
   - Validate correct element was targeted
   - Check element attributes and relationships
   - Verify element state changes

3. **Success Criteria**
   - Correct element identified and interacted with
   - Expected visual changes occurred
   - No unintended side effects

## Output Format

```json
{
    "total_tasks": 10,
    "successful_tasks": 8,
    "evaluations": [
        {
            "task_id": "task_001",
            "success": true,
            "evaluation": "Detailed evaluation text...",
            "timestamp": 1234567890
        },
        ...
    ]
}
```

## Requirements

- OpenAI API key with GPT-4V access
- Python 3.8+
- Required packages in `requirements.txt`
