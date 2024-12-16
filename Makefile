.PHONY: install test lint format clean run evaluate

# Environment setup
install:
	pip install -e .
	pip install -r requirements.txt

# Testing
test:
	pytest

# Code quality
lint:
	flake8 .
	mypy .
	black . --check
	isort . --check

format:
	black .
	isort .

# Cleaning
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name "*.egg" -exec rm -r {} +

# Benchmark commands
run:
	python run.py \
		--tasks data/dom_tasks.jsonl \
		--output results/run_001 \
		--headless \
		--save-accessibility-tree

evaluate:
	python evaluation/auto_eval.py \
		--tasks data/dom_tasks.jsonl \
		--results results/run_001 \
		--ground-truth data/ground_truth \
		--output results/run_001/evaluation.json
