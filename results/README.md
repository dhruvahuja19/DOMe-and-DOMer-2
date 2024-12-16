# Results Directory

This directory stores benchmark results and evaluations.

## Directory Structure

```
results/
├── run_001/                 # Each run in its own directory
│   ├── results.json        # Raw results from model
│   ├── evaluation.json     # Evaluation scores
│   └── screenshots/        # Before/after screenshots
├── run_002/
└── ...
```

## File Formats

### `results.json`
```json
{
    "task_id": "task_001",
    "action": {
        "type": "click",
        "value": null
    },
    "html_element": "<button class=\"search-btn\">...</button>",
    "confidence": 0.95,
    "screenshots": {
        "before": "before_001.png",
        "after": "after_001.png"
    }
}
```

### `evaluation.json`
```json
{
    "task_id": "task_001",
    "visual_evaluation": {
        "score": 0.95,
        "details": "..."
    },
    "html_evaluation": {
        "score": 0.92,
        "structure_score": 0.95,
        "attributes_score": 0.90,
        "content_score": 0.89
    },
    "final_score": 0.94,
    "success": true
}
```

## Guidelines

1. **Organization**
   - Create a new directory for each benchmark run
   - Use consistent naming: `run_XXX`
   - Keep screenshots organized by task

2. **Storage**
   - Clean up old runs periodically
   - Compress screenshots if needed
   - Back up important results

3. **Analysis**
   - Use evaluation.json for metrics
   - Compare runs to track improvements
   - Document significant changes
