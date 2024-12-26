# DOM and DOMer-2

A First-in-Class Benchmark for Evaluating the Ability of Web Agents to Identify and Interact with Web Components

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
- anthropic
- google-generativeai
- python-dotenv

3. Set up your API keys in a `.env` file:
```bash
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_API_KEY=your_google_key_here
```

## Supported Models

The benchmark currently supports the following models:

1. **GPT-4 Turbo** (OpenAI)
   - Default model for both task execution and evaluation
   - High accuracy but subject to rate limits (3500 RPM)

2. **Claude 3 Haiku** (Anthropic)
   - Fast and efficient for task execution
   - Subject to stricter rate limits (5 RPM)
   - Use `--serial` flag for best results

3. **Gemini 1.5 Pro** (Google)
   - Latest version of Google's Gemini model
   - Good balance of speed and accuracy

## Usage

The benchmark can be run in either serial or parallel mode:

### Parallel Mode (Default)
```bash
# Run with GPT-4
python -m benchmark --model gpt4 --tasks data/test_tasks.jsonl --output-dir results

# Run with Claude
python -m benchmark --model claude --tasks data/test_tasks.jsonl --output-dir results --serial

# Run with Gemini
python -m benchmark --model gemini --tasks data/test_tasks.jsonl --output-dir results
```

### Serial Mode
```bash
python -m benchmark --model [gpt4|claude|gemini] --tasks data/test_tasks.jsonl --output-dir results --serial
```

### Evaluation
Results are automatically evaluated using GPT-4V for visual comparison and GPT-4 for HTML structure matching:

```bash
python -m evaluate --tasks data/test_tasks.jsonl --results-dir results --output results/evaluation.json
```

## Task Format

Tasks are defined in JSONL format with the following structure:
```json
{
    "web_name": "Website Name",
    "id": "unique_task_id",
    "task": "Description of the interaction task",
    "web": "https://website.url",
    "element_type": "button|input|link",
    "interaction": "click|type|hover",
    "target_element": {
        "type": "id|class|xpath",
        "value": "selector_value"
    },
    "input_text": "Text to type (for type interactions)",
    "target_html": "HTML of target element",
    "ground_truth": {
        "screenshot": "path/to/screenshot.png",
        "description": "Expected result description"
    }
}
```

## Rate Limits

Different models have different rate limits:
- GPT-4: 3500 requests per minute
- Claude: 5 requests per minute
- Gemini: 60 requests per minute

Use the `--serial` flag for models with strict rate limits (e.g., Claude) to avoid hitting limits.

## Test Tasks

The repository includes two task sets:
- `data/test_tasks.jsonl`: Full test set with 100+ tasks
- `data/test_tasks_10.jsonl`: Smaller set of 10 tasks for quick testing

## Detailed Setup Instructions
- **Environment Configuration**: Copy `.env.example` to `.env` and fill in your API keys.
- **Dependencies**: Install dependencies using `pip install -r requirements.txt`.
- **Virtual Environment**: (Optional) Set up a virtual environment using `venv`.

## Running Benchmarks
- **Main Script**: Use `run.py` to execute benchmarks. Example:
  ```bash
  python run.py --tasks data/test_tasks.jsonl --output results --model gpt4
  ```
- **Parallel and Serial Execution**: Use `parallel_runner.py` or `serial_runner.py` for specific execution modes.

## Adding New Models
- **Model Class**: Create a new class in `models/` inheriting from `BaseModel`.
- **Integration**: Implement required methods and integrate with `run.py`.
- **Testing**: Validate the new model with existing task sets.

## Interpreting Results
- **Results Directory**: Check the `results/` directory for output files and logs.
- **Evaluation**: Use `evaluate.py` to assess model performance.
- **Logs**: Review logs for insights into model behavior and errors.

## Baseline Results
- **Reference Scores**: Baseline results are available in `results/baseline_results/`.
- **Comparison**: Use these scores to evaluate new models or configurations.

## Additional Resources
- **Scripts**: Explore the `scripts/` directory for additional utilities.
- **Examples**: Check the `examples/` directory for example usage and configurations.
- **Utilities**: Use `utils.py` and other scripts in `utils/` for common tasks.

## Documentation

### Using the Benchmark
- **Setup**: Ensure all dependencies are installed and API keys are configured in the `.env` file.
- **Running Tests**: Use the `benchmark` module to run tests on different models. Specify the model and task set.
- **Serial vs Parallel**: Use `--serial` for models with strict rate limits.

### Adding New Agents
- **Model Integration**: Implement a new model class inheriting from `BaseModel`.
- **Configuration**: Configure API keys and model parameters in the new class.
- **Testing**: Add the new model to the benchmark script and test with existing task sets.

### Interpreting Results
- **Output Files**: Check the `results` directory for detailed logs and evaluation scores.
- **Error Handling**: Review logs for any errors or skipped tasks.
- **Baseline Comparison**: Compare results against baseline scores provided in the `baseline_results` directory.

### Baseline Results
- Baseline results for each model are available for comparison.
- Use these results to gauge the performance of new models or configurations.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
