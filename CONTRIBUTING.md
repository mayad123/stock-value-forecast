# Contributing

## Before you start

1. **Environment setup.** Follow [Development](README.md#development) in the README: clone, create a venv, install `requirements.txt` and optionally `requirements-dev.txt`.
2. **Run lint and tests locally.** CI runs the same checks; fix any failures before opening a PR.
   ```bash
   make lint
   make test
   ```
   Or run the minimal integration test only: `make test-integration`.

## Pull requests

- Open PRs against `main` (or `master`). CI will run:
  - **Lint** (Ruff)
  - **Tests** (full pytest suite on Python 3.10 and 3.11)
  - **Integration** (minimal pipeline: build-features on tiny data)
- **All CI jobs must pass** before merge. To enforce this, configure [branch protection](README.md#ci-and-branch-protection) so that the **CI** status check is required.
- Keep PRs focused; run `make lint` and `make test` before pushing.
