# Contributing to Mai CLI

Thank you for your interest in contributing!

## Process

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feat/my-feature`
3. **Make your changes** — add tests, update docs
4. **Run tests**: `pytest tests/ -v`
5. **Commit** with a clear message
6. **Open a Pull Request**

## Requirements

### Tests
All PRs must pass `pytest tests/ -v`. Add tests for any new functionality.

### Code Style
Follow [PEP 8](https://pep8.org/). Run `pip install flake8 && flake8 src/` before committing.

### Commit Messages
- Use imperative mood: `Add feature` not `Added feature`
- Reference issues: `Closes #123`

## Issue Templates

When opening an issue, please include:
- Python version and OS
- Command executed and full error output
- Expected vs actual behavior
- Minimal reproduction steps
