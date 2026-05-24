# Contributing to WireGuard Auto

First off, thank you for considering contributing to WireGuard Auto! We appreciate the community's help in making this open-source project better, more secure, and more accessible.

## Contact Us
For any major architectural changes or core questions, feel free to contact the lead developers:
- **Lead Developer**: Antony Ngemu
- **Email**: ngemuantony@tuinnov8.com
- **Website**: [www.tuinov8.com](https://www.tuinov8.com)

## Code of Conduct
By participating in this project, you agree to abide by professional and respectful conduct. Harassment, discrimination, or abusive behavior will not be tolerated.

## How Can I Contribute?

### Reporting Bugs
If you find a bug in the source code, you can help us by submitting an issue. Please make sure to include:
- A clear descriptive title.
- Steps to reproduce the bug.
- Environment details (e.g., Docker version, Linux distribution, Python version).

### Suggesting Enhancements
Enhancement suggestions are highly welcomed! Please open an issue to describe your feature request and its potential use case before writing the code. This ensures we are aligned on the project's roadmap.

### Pull Requests
1. **Fork the Repository**: Create a fork of the `wg-auto` project.
2. **Create a Branch**: Make your changes in a specific branch (e.g., `feature/add-new-dashboard` or `bugfix/fix-key-cache`).
3. **Commit Messages**: Ensure your commit messages are descriptive and concise.
4. **Code Quality**: Ensure the code follows standard PEP 8 guidelines. If writing tests, ensure they pass.
5. **Submit PR**: Submit a Pull Request targeting the `main` branch. Provide a detailed summary of your changes in the PR description.

## Development Setup

1. Copy `.env.example` to `.env` and fill out necessary secrets.
2. Initialize the project: `docker-compose up -d --build`
3. Verify tests (if applicable) and check the Django logs using `docker-compose logs -f`.

Thank you for contributing to the Tuinnov8 ecosystem!
