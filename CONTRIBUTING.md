# Contributing to KRAG Video Platform

Thank you for your interest in contributing to the KRAG Video Platform! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Architecture Decisions](#architecture-decisions)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/krag-video-platform.git
   cd krag-video-platform
   ```
3. **Add the upstream remote**:
   ```bash
   git remote add upstream https://github.com/your-org/krag-video-platform.git
   ```

## Development Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (including dev dependencies)
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Copy environment template
cp configs/.env.example configs/.env

# Start infrastructure services
docker-compose up -d

# Run tests to verify setup
pytest tests/
```

### Running the Application

```bash
# Start the API server
uvicorn src.api.main:app --reload

# Run a specific agent
python -m src.agents.story_parser
```

## Coding Standards

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use [Black](https://black.readthedocs.io/) for formatting (line length: 88)
- Use [Ruff](https://docs.astral.sh/ruff/) for linting
- Use type hints for all function signatures
- Use [Pydantic](https://docs.pydantic.dev/) for data models

### Code Quality Tools

All code must pass the following checks before merge:

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check
mypy src/

# Run tests
pytest tests/
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `StoryParserAgent` |
| Functions | snake_case | `parse_scene_text` |
| Variables | snake_case | `scene_graph` |
| Constants | UPPER_SNAKE | `MAX_ITERATIONS` |
| Files | snake_case | `story_parser.py` |

### Documentation

- All public functions and classes must have docstrings
- Use Google-style docstrings
- Update documentation when changing functionality

```python
def parse_text(text: str, config: ParsingConfig) -> list[TextSegment]:
    """Parse raw text into structured segments.

    Args:
        text: The raw text to parse.
        config: Configuration for parsing behavior.

    Returns:
        A list of parsed text segments.

    Raises:
        ParsingError: If the text cannot be parsed.
    """
    pass
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-shot-planning` - New features
- `fix/scene-boundary-detection` - Bug fixes
- `docs/update-agent-spec` - Documentation
- `refactor/extract-embedding-client` - Refactoring
- `test/add-parser-unit-tests` - Tests

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat(agents): add story parser agent with NER support

- Implement scene boundary detection
- Add character extraction using spaCy
- Include unit tests for edge cases

Closes #42
```

### Testing

- Write tests for all new functionality
- Maintain or improve code coverage
- Use `pytest` for testing
- Place tests in `tests/` mirroring `src/` structure

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/agents/test_story_parser.py

# Run tests matching pattern
pytest -k "test_parse"
```

## Pull Request Process

### Before Submitting

1. **Sync with upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**:
   ```bash
   black src/ tests/
   ruff check src/ tests/
   mypy src/
   pytest tests/
   ```

3. **Update documentation** if needed

4. **Add changelog entry** for user-facing changes

### Submitting

1. Push your branch to your fork
2. Open a Pull Request against `main`
3. Fill out the PR template completely
4. Link any related issues

### PR Requirements

- [ ] All CI checks pass
- [ ] Code is formatted and linted
- [ ] Tests are included for new functionality
- [ ] Documentation is updated
- [ ] Changelog is updated (if applicable)
- [ ] At least one approval from maintainers

### Review Process

1. Maintainers will review within 2-3 business days
2. Address feedback in new commits
3. Once approved, maintainer will merge

## Architecture Decisions

### ADR Process

Significant architecture decisions are documented in `docs/adr/`.

Before making major changes:

1. Create an ADR document
2. Discuss in an issue or PR
3. Get approval from maintainers
4. Implement the change

ADR Template: `docs/adr/template.md`

### What Requires an ADR?

- New external dependencies
- Changes to data models
- New agent implementations
- Pipeline stage modifications
- Infrastructure changes
- API changes

## Questions?

- Open a [Discussion](https://github.com/your-org/krag-video-platform/discussions)
- Check existing [Issues](https://github.com/your-org/krag-video-platform/issues)
- Review the [Documentation](docs/)

Thank you for contributing!
