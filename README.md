# DOM and DOMer-2

A benchmark for evaluating language models' ability to execute web element interactions.

## Overview

DOM and DOMer-2 focuses on testing a model's ability to interact with web elements (clicking buttons, typing text, etc.) without requiring complex planning or reasoning. The benchmark provides:

1. Simple, single-action tasks
2. Real websites with diverse DOM structures
3. Ground truth screenshots for validation
4. GPT-4V based evaluation
5. Support for both serial and parallel execution

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/DOMe-and-DOMer-2.git
cd DOMe-and-DOMer-2
```

2. Install dependencies using pip:
```bash
pip install -e .
```

Required dependencies:
- selenium
- webdriver-manager
- Pillow
- numpy
- requests
- beautifulsoup4
- openai
- python-dotenv

3. Set up your OpenAI API key in a `.env` file:
```bash
OPENAI_API_KEY=your_api_key_here
```

## Usage

The benchmark can be run in either serial or parallel mode:

### Parallel Mode (Default)
```bash
python run.py --tasks data/dom_tasks.jsonl --output results --max-workers 4 --evaluate
```

### Serial Mode
```bash
python run.py --tasks data/dom_tasks.jsonl --output results --mode serial --evaluate
```

### Key Arguments
- `--tasks`: Path to JSONL file containing tasks
- `--output`: Output directory for results
- `--mode`: Run tasks in 'serial' or 'parallel' mode (default: parallel)
- `--max-workers`: Number of parallel workers (default: 4)
- `--evaluate`: Run GPT-4V evaluation after tasks complete
- `--evaluate-mode`: Run evaluations in 'serial' or 'parallel' mode (default: parallel)
- `--save-accessibility-tree`: Save accessibility trees for each task
- `--wait-time`: Wait time between actions in seconds (default: 2.0)

## Directory Structure

```
DOMe-and-DOMer-2/
├── data/
│   ├── dom_tasks.jsonl         # Task definitions
│   └── task_schema.json        # JSON schema for tasks
├── evaluation/
│   ├── auto_eval.py           # Evaluation orchestrator
│   ├── parallel_eval.py       # Parallel evaluation implementation
│   ├── image_match.py         # GPT-4V image comparison
│   └── fuzzy_match.py         # HTML structure comparison
├── parallel_runner.py         # Parallel task execution
├── serial_runner.py          # Serial task execution
├── utils.py                  # Shared utilities
├── run.py                    # Main entry point
└── pyproject.toml           # Project configuration and dependencies

## Output Structure

Results are saved in the specified output directory:
```
output_dir/
├── results.json              # Task execution results
├── evaluation.json           # GPT-4V evaluation results
├── benchmark.log            # Execution logs
├── *_before.png            # Screenshots before interaction
├── *_after.png             # Screenshots after interaction
└── *_tree.json            # Accessibility trees (if enabled)
```

## Task Format

Tasks are defined in `data/dom_tasks.jsonl`:

```json
{
    "id": "task_id",
    "task": "Click the search box and type 'hello'",
    "web": "https://example.com",
    "interaction": "type",
    "target_element": {
        "type": "css",
        "value": "#searchbox"
    },
    "input_text": "hello",
    "ground_truth": {
        "screenshot": "path/to/ground_truth.png"
    }
}
```

## Evaluation

The benchmark uses GPT-4V to evaluate task success by comparing:
1. Before/after screenshots with ground truth
2. DOM structure changes
3. Task completion criteria

Evaluation can be run in parallel or serial mode and produces detailed scoring and reasoning for each task.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
