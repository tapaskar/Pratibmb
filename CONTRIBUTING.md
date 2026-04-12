# Contributing to Pratibmb

Thank you for your interest in contributing to Pratibmb! This is an open-source desktop app for chatting with your past self using local AI, licensed under AGPLv3 with a commercial dual-license option.

We welcome contributions of all kinds -- bug reports, feature requests, documentation improvements, and code changes.

## How to Contribute

- **Report bugs** by opening a [GitHub Issue](../../issues). Include steps to reproduce, expected behavior, and your OS/version.
- **Suggest features** by opening a GitHub Issue with a clear description of the use case.
- **Improve documentation** by submitting a pull request with your changes.
- **Submit code** by following the pull request process described below.

## Development Setup

1. Clone the repository:
   ```
   git clone https://github.com/Tapaskar/Pratibmb.git
   cd Pratibmb
   ```

2. Install the Python package in editable mode:
   ```
   pip install -e .
   ```

3. Set up the desktop app:
   ```
   cd desktop
   npm install
   cargo tauri dev
   ```

Make sure you have Python, Node.js, npm, and the [Tauri prerequisites](https://tauri.app/start/prerequisites/) installed for your platform.

## Code Style Guidelines

- **Python** -- Follow [PEP 8](https://peps.python.org/pep-0008/).
- **Rust** -- Format with `cargo fmt` and check with `cargo clippy`.
- **JavaScript / HTML** -- Keep the existing style consistent with the surrounding code.

Keep commits focused. Each commit should represent a single logical change.

## Pull Request Process

1. **Fork** the repository and create a new branch from `main`.
2. **Make your changes** on the branch, following the code style guidelines above.
3. **Test** your changes locally to make sure nothing is broken.
4. **Commit** with a clear message. Include a DCO sign-off line (see CLA section below):
   ```
   git commit -s -m "Description of the change"
   ```
5. **Push** your branch and open a pull request against `main`.
6. A maintainer will review your PR. Please be responsive to feedback.

## Contributor License Agreement (CLA)

This project uses a dual-license model: AGPLv3 for open-source use and a separate commercial license. To keep this possible without needing individual permission from every contributor, we use a lightweight sign-off CLA. No separate form is required.

By submitting a pull request with a `Signed-off-by` line in your commit message, you agree to the following:

1. Your contribution is licensed under the **GNU Affero General Public License v3.0 (AGPLv3)**, consistent with the rest of the project.
2. You grant the project maintainer a **perpetual, worldwide, non-exclusive, royalty-free right** to include your contribution under the project's commercial license.
3. You confirm that you have the right to make this contribution and that it does not violate any third-party rights.

Add the sign-off line to your commits automatically by using the `-s` flag:

```
git commit -s -m "Your commit message"
```

This appends a line like `Signed-off-by: Your Name <your@email.com>` to the commit message, which serves as your agreement to the terms above.

## Reporting Bugs

Please use [GitHub Issues](../../issues) to report bugs. A good bug report includes:

- A clear, descriptive title.
- Steps to reproduce the problem.
- What you expected to happen and what actually happened.
- Your operating system and version.
- Any relevant logs or screenshots.

## Contact

For questions that do not fit into a GitHub Issue, reach out at **admin@sparkupcloud.com**.
