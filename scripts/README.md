# Scripts Directory

This directory contains utility scripts for managing and maintaining the benchmark.

## Scripts

### `add_target_html.py`
- Adds empty `target_html` field to task definitions
- Used for upgrading existing task files to support HTML validation
- Usage: `python add_target_html.py`

## Adding New Scripts

When adding new utility scripts:
1. Follow Python best practices
2. Add proper error handling
3. Document usage in this README
4. Include example commands if applicable

## Script Guidelines

1. **File Naming**
   - Use descriptive names
   - Separate words with underscores
   - End with `.py` extension

2. **Documentation**
   - Add docstrings to all functions
   - Include usage examples
   - Document any dependencies

3. **Error Handling**
   - Handle file I/O errors
   - Provide meaningful error messages
   - Add logging where appropriate

4. **Testing**
   - Add test cases if possible
   - Include sample data if needed
   - Document test procedures
