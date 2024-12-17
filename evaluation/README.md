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

## Environment Setup

1. Ensure you have the OpenAI API key in your `.env` file:
```bash
OPENAI_API_KEY=your_openai_api_key
```

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

## Evaluation Process

1. **Visual Validation (GPT-4V)**
   - Compares before/after screenshots with ground truth
   - Considers task-specific requirements
   - Returns a score and detailed reasoning

2. **HTML Element Validation**
   - Compares target HTML with actual interaction
   - Uses fuzzy matching for robustness
   - Considers element attributes and structure

The final score is a weighted average:
- Visual Score: 60%
- HTML Score: 40%

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
      "html_score": 0.90,
      "final_score": 0.93,
      "reasoning": "..."
    }
  ]
}
```
