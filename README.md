# DOM and DOMer-2

A benchmark for evaluating language models' ability to execute web element interactions.

## Overview

DOM and DOMer-2 focuses on testing a model's ability to interact with web elements (clicking buttons, typing text, etc.) without requiring complex planning or reasoning. The benchmark provides:

1. Simple, single-action tasks
2. Real websites with diverse DOM structures
3. Ground truth screenshots for validation
4. GPT-4V based evaluation

## Directory Structure

```
DOMe-and-DOMer-2/
├── data/
│   ├── dom_tasks.jsonl         # Task definitions
│   └── ground_truth/          # Ground truth screenshots
│       ├── amazon_search_1_gt.png
│       └── ...
├── evaluation/
│   ├── auto_eval.py           # GPT-4V evaluation script
│   └── README.md              # Evaluation documentation
├── results/                   # Results for each run
│   └── run_001/
│       ├── before_*.png       # Screenshots before interaction
│       ├── after_*.png        # Screenshots after interaction
│       ├── accessibility_*.json  # Accessibility trees
│       ├── results.json       # Raw results
│       ├── evaluation.json    # GPT-4V evaluations
│       └── benchmark.log      # Detailed logs
├── prompts.py                # LLM system prompts
├── run.py                    # Main benchmark runner
├── utils.py                 # Utility functions
└── requirements.txt         # Dependencies

## Task Format

Tasks are defined in `data/dom_tasks.jsonl`:

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
    "target_html": "<input id='searchword' type='text' ...>",
    "ground_truth": {
        "screenshot": "evaluation/ground_truth/task_1_gt.png",
        "description": "The word 'hello' has been entered in the search box"
    }
}
```

Key fields:
- `target_element`: Selector information for finding the element
- `target_html`: Expected HTML structure of the element
- `ground_truth`: Reference screenshot and description

## Ground Truth

Ground truth is provided in two forms:
1. **Screenshots**: Visual state after successful interaction
2. **Descriptions**: Text description of expected changes

Located in `data/ground_truth/`, each task has:
- `[task_id]_gt.png`: Screenshot of successful interaction
- Description in task JSON explaining expected changes

## Environment Setup

1. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Set up environment variables in `.env`:
```bash
OPENAI_API_KEY=your_openai_api_key
```

## Running the Benchmark

```bash
python run.py --tasks data/dom_tasks.jsonl --output data/results --evaluate
```

This will:
1. Execute each task in the tasks file
2. Save screenshots and results
3. Compare actual HTML elements with expected ones
4. Run GPT-4V evaluation on screenshots

## Ground Truth Management

Ground truth images are stored in `evaluation/ground_truth/` with a consistent naming scheme:
```
evaluation/ground_truth/
└── task_1_gt.png
└── task_2_gt.png
...
```

The tasks file references these images using relative paths:
```json
{
  "id": 1,
  "ground_truth": {
    "screenshot": "evaluation/ground_truth/task_1_gt.png"
  }
}
```

## Testing

Run environment tests:
```bash
python test_env.py
```

Run OpenAI API connection test:
```bash
python test_openai.py
```

## Evaluation Process

1. **Technical Validation**:
   - Element found and interacted with
   - No errors during interaction
   - Accessibility tree verification

2. **Visual Validation**:
   - Compare after screenshot with ground truth
   - Verify expected visual changes
   - Check for unintended side effects

3. **GPT-4V Analysis**:
   - Compare before/after/ground-truth screenshots
   - Verify interaction success
   - Check visual state matches expectations

## Output Format

```json
{
    "total_tasks": 10,
    "successful_tasks": 8,
    "evaluations": [
        {
            "task_id": "amazon_search_1",
            "success": true,
            "evaluation": "Detailed evaluation text...",
            "timestamp": 1234567890
        }
    ]
}
```

## Requirements

- Python 3.8+
- Chrome/Chromium browser
- OpenAI API key (for evaluation)
- Required packages in `requirements.txt`

## Contributing

[Contributing guidelines will be added]

## License

[License information will be added]
