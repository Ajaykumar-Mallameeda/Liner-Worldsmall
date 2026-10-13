# Contributing to AI Vessel Routing System

## Welcome

Thank you for considering contributing to the AI Vessel Routing System. This project combines operations research, AI/LLM agent coordination, and production-grade frontend engineering.

## Code of Conduct

By participating, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Issues

- Check existing issues before creating a new one
- Use a clear, descriptive title
- Include steps to reproduce, expected behavior, and actual behavior
- Attach relevant logs, screenshots, or `pipeline_output.json` excerpts

### Suggesting Features

- Explain the problem you're solving
- Describe the solution with concrete examples
- Consider whether the change requires backend modifications (backend is frozen for V1)

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run the backend test suite: `pytest tests/`
5. Build the frontend: `cd frontend && npm run build`
6. Verify the runtime truth: check that `pipeline_output.json` values match certification
7. Commit with a descriptive message
8. Push and open a Pull Request

### Commit Guidelines

- Use present tense ("Add feature" not "Added feature")
- Reference issue numbers when applicable
- Keep commits focused on single changes

## Development Setup

See [README.md](README.md#-quick-start) for setup instructions.

## Architecture Overview

The system has two main layers:

1. **Backend** (`src/`): Python optimization engine with GA, MILP, and AI agents
2. **Frontend** (`frontend/`): React dashboard consuming `pipeline_output.json`

Both layers are independently runnable. The backend produces `pipeline_output.json` which the frontend reads as its single source of truth.

## Backend is Frozen for V1

The optimization algorithms, AI agents, prompt layer, validators, consensus engine, and shared context are **frozen** and should NOT be modified during V1. Only frontend improvements and documentation changes are accepted at this stage.
