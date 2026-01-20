# Contributing to DeniDin

Thank you for your interest in contributing to DeniDin! This document provides guidelines and best practices for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Documentation](#documentation)

---

## Code of Conduct

Be respectful, inclusive, and collaborative. This project follows standard open-source community guidelines.

---

## Getting Started

### Prerequisites

- Python 3.8+ (Python 3.11 recommended)
- Git
- Green API account (for WhatsApp integration)
- OpenAI API key

### Setup Development Environment

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/yourusername/DeniDin.git
   cd DeniDin/denidin-bot
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # venv\Scripts\activate   # On Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up configuration**:
   ```bash
   cp config/config.example.json config/config.json
   # Edit config/config.json with your credentials
   ```

5. **Run tests to verify setup**:
   ```bash
   python3 -m pytest tests/ -v
   ```

---

## Development Workflow

### 1. Test-Driven Development (TDD) **[REQUIRED]**

DeniDin follows **strict TDD principles** as defined in the project Constitution. All features MUST be developed using this workflow:

#### TDD Workflow Steps:

1. **Write Tests First** (T###a tasks):
   - Create comprehensive tests covering all acceptance criteria
   - Include happy path, edge cases, and error scenarios
   - Mock external dependencies (Green API, OpenAI)
   - Follow naming convention: `test_<feature>_<scenario>`

2. **Human Approval Gate** 👤:
   - **STOP**: Do not proceed without approval
   - Submit tests for review via Pull Request
   - Tests must be approved before implementation begins
   - Address any feedback and get explicit approval

3. **Implement Code** (T###b tasks):
   - Write **minimum code** to pass approved tests
   - Tests are now **IMMUTABLE** (locked)
   - No test changes without re-approval

4. **Validate**:
   - Run tests: `pytest tests/ -v`
   - All tests must pass before PR creation

5. **Iterate**:
   - Repeat for next feature

#### Test Immutability Principle 🔒

**Once tests for a phase are approved and passing, they are IMMUTABLE.**

- ❌ **DO NOT** modify existing passing tests without **EXPLICIT HUMAN APPROVAL**
- ✅ **DO** add new tests for new features
- ❌ **DO NOT** change test assertions to "fix" failing tests
- ✅ **DO** fix the implementation code to pass existing tests

**If you absolutely must change a test:**
1. Provide **clear justification** explaining why
2. Get **explicit human approval** in PR comments
3. Tag commit with `HUMAN APPROVED: <reason>`
4. Document the change in PR description

**Examples:**

```bash
# ❌ WRONG - Changing existing test without approval
git commit -m "Fix test by adjusting expected value"

# ✅ CORRECT - Test change approved
git commit -m "HUMAN APPROVED: Update test fixture for UTC timestamps per Constitution"
```

### 2. Feature Branch Workflow

**NEVER commit directly to `master`!** All work must go through feature branches and Pull Requests.

```bash
# Create a new feature branch
git checkout -b 001-phase#-feature-description

# Example:
git checkout -b 001-phase7-polish
git checkout -b 002-conversation-context
```

### 3. Commit Messages

Follow this format for commits:

```
[T###] Brief description (50 chars max)

Detailed explanation if needed (wrap at 72 chars).
Include context, motivation, and technical decisions.

Closes #issue-number
```

**Examples:**
```
[T049] Add comprehensive docstrings to all classes

Adds Google-style docstrings with Args, Returns, and Raises
sections to all public methods in src/ directory.

[T053] Run full test suite with 89% coverage

Executes 142 tests with pytest-cov, generates HTML report.
Coverage exceeds 80% target (89% achieved).
```

---

## Code Style

### Python Code Standards

DeniDin follows **PEP 8** with the following conventions:

#### General Guidelines

- **Line Length**: Maximum 120 characters (configured in `.pylintrc`)
- **Indentation**: 4 spaces (no tabs)
- **Encoding**: UTF-8
- **Quotes**: Prefer single quotes for strings, double for docstrings

#### Naming Conventions

- **Functions/Methods**: `snake_case` (e.g., `process_notification()`)
- **Classes**: `PascalCase` (e.g., `WhatsAppHandler`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_MESSAGE_LENGTH`)
- **Private Methods**: `_leading_underscore` (e.g., `_send_with_retry()`)

#### Configuration Guidelines

- **NO environment variables**: All configuration MUST be in `config/config.json`
- **NO os.getenv()**: Do not use environment variables for any configuration
- **Feature flags**: Use `config.feature_flags` dictionary for feature toggles
- **Secrets**: Store API keys and tokens in `config/config.json` (excluded from git via `.gitignore`)
- **Example config**: Always maintain `config/config.example.json` with safe placeholder values

#### Imports

**Order** (enforced by linter):
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# ✅ CORRECT
import os
import sys
from typing import Optional

import requests
from openai import OpenAI

from src.models.message import WhatsAppMessage
from src.utils.logger import get_logger
```

```python
# ❌ WRONG - Mixed order
from src.models.message import WhatsAppMessage
import os
from openai import OpenAI
```

#### Docstrings

Use **Google-style docstrings** for all public classes and methods:

```python
def process_notification(self, notification: Notification) -> WhatsAppMessage:
    """
    Process a Green API notification into a WhatsAppMessage.
    
    Args:
        notification: Green API notification object containing message data
        
    Returns:
        WhatsAppMessage object with parsed data
        
    Raises:
        ValueError: If notification format is invalid
    """
    # Implementation here
```

#### Type Hints

**Always include type hints** on function signatures:

```python
# ✅ CORRECT
def create_request(self, message: WhatsAppMessage) -> AIRequest:
    pass

def get_logger(name: str, log_level: str = 'INFO') -> logging.Logger:
    pass
```

```python
# ❌ WRONG - Missing type hints
def create_request(self, message):
    pass
```

### Code Quality Tools

Run these checks before submitting a PR:

```bash
# Linter (target: 8.0+/10)
python3 -m pylint src/ denidin.py --rcfile=.pylintrc

# Type checker
python3 -m mypy src/ --config-file=mypy.ini

# Auto-format imports
python3 -m isort src/ denidin.py

# Remove trailing whitespace
find src/ -name "*.py" -exec sed -i '' 's/[[:space:]]*$//' {} \;
```

**Expected Results:**
- Pylint: ≥ 8.0/10 (current: 8.35/10)
- Mypy: 0 type errors (with configured ignores)
- All tests passing: 142/142

---

## Testing

### Test Structure

```
tests/
├── unit/               # Fast, mocked tests
│   ├── test_config.py
│   ├── test_message.py
│   ├── test_*_handler.py
│   └── ...
├── integration/        # Component interaction tests
│   ├── test_bot_startup.py
│   ├── test_message_flow.py
│   └── ...
└── fixtures/           # Test data
    └── sample_messages.json
```

### Writing Tests

#### Unit Tests (Mocked)

Use pytest with mocks for external dependencies:

```python
import pytest
from unittest.mock import Mock, patch
from src.handlers.ai_handler import AIHandler

def test_get_response_handles_timeout(mock_openai_client, config):
    """Test AIHandler gracefully handles API timeouts."""
    handler = AIHandler(mock_openai_client, config)
    mock_openai_client.chat.completions.create.side_effect = APITimeoutError("Timeout")
    
    request = AIRequest(...)
    response = handler.get_response(request)
    
    assert "trouble connecting" in response.response_text
```

#### Integration Tests (Real-ish)

Test component interactions with minimal mocking:

```python
def test_complete_message_flow():
    """Test end-to-end message flow from WhatsApp to OpenAI."""
    # Setup
    config = BotConfiguration.from_file('config/config.json')
    whatsapp_handler = WhatsAppHandler()
    ai_handler = AIHandler(openai_client, config)
    
    # Execute
    message = whatsapp_handler.process_notification(notification)
    ai_request = ai_handler.create_request(message)
    ai_response = ai_handler.get_response(ai_request)
    
    # Verify
    assert ai_response.response_text
    assert ai_response.tokens_used > 0
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/unit/test_message.py -v

# Specific test function
pytest tests/unit/test_message.py::test_from_notification_parses_correctly -v

# With coverage
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html to view coverage

# Fast (unit tests only)
pytest tests/unit/ -v

# Slow (integration tests, may consume API quota)
pytest tests/integration/ -v
```

### Test Coverage Requirements

- **Minimum**: 80% overall coverage
- **Target**: 90% coverage
- **Current**: 89% coverage ✅

Check coverage:
```bash
pytest tests/ --cov=src --cov-report=term
```

---

## Pull Request Process

### Before Submitting PR

✅ **Checklist:**
- [ ] Tests written and approved (TDD workflow followed)
- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Code linted (`pylint src/ denidin.py`)
- [ ] Type hints added (`mypy src/`)
- [ ] Docstrings on all public methods
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No merge conflicts with `master`

### Creating a Pull Request

1. **Push your branch**:
   ```bash
   git push origin 001-phase7-polish
   ```

2. **Open PR on GitHub**:
   - Title: `[Phase #] Brief description`
   - Description: Include:
     - What changed
     - Why it changed
     - How to test
     - Screenshots (if applicable)
     - Related issue numbers

3. **PR Template**:
   ```markdown
   ## Description
   Brief summary of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update

   ## Testing
   - [ ] Unit tests added
   - [ ] Integration tests added
   - [ ] All tests passing (142/142)
   - [ ] Manual testing completed

   ## Checklist
   - [ ] TDD workflow followed
   - [ ] Code linted (≥8.0/10)
   - [ ] Type hints added
   - [ ] Docstrings complete
   - [ ] No test immutability violations

   Closes #123
   ```

### Review Process

1. **Automated Checks** (if CI/CD configured):
   - Tests must pass
   - Linter must pass
   - Coverage must be ≥80%

2. **Code Review**:
   - At least one approval required
   - Address all feedback
   - Re-request review after changes

3. **Merge**:
   - **Squash and merge** preferred for clean history
   - Delete branch after merge
   - Update local master: `git checkout master && git pull`

---

## Documentation

### Updating Documentation

When adding features, update:

1. **README.md**: User-facing changes, new features
2. **DEPLOYMENT.md**: Production deployment changes
3. **specs/**: Technical specifications (for major features)
4. **Docstrings**: All new classes/methods

### Specification-Driven Development

For **major features**, follow the full spec workflow:

1. **Create Specification** (`specs/###-feature-name/spec.md`):
   - User scenarios (Given-When-Then)
   - Functional requirements
   - Success criteria

2. **Create Plan** (`specs/###-feature-name/plan.md`):
   - Technical design
   - Data models
   - API contracts

3. **Create Tasks** (`specs/###-feature-name/tasks.md`):
   - TDD task pairs (T###a, T###b)
   - Dependency graph
   - Version control workflow

4. **Implement** (follow TDD workflow)

---

## Common Tasks

### Adding a New Handler

1. Write tests: `tests/unit/test_new_handler.py`
2. Get approval
3. Implement: `src/handlers/new_handler.py`
4. Add docstrings
5. Update README.md

### Adding a New Model

1. Write tests: `tests/unit/test_new_model.py`
2. Get approval
3. Implement: `src/models/new_model.py`
4. Add type hints and docstrings
5. Update `data-model.md` (if major)

### Fixing a Bug

1. Write failing test that reproduces bug
2. Fix bug in implementation
3. Verify test now passes
4. Add regression test if needed
5. Document in commit message

---

## Questions?

- Check existing issues: [GitHub Issues](https://github.com/yourusername/DeniDin/issues)
- Review project docs: `specs/001-whatsapp-chatbot-passthrough/`
- Ask in PR comments
- Contact maintainers

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.
