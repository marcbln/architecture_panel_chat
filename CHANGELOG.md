# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-26

### Changed
- `list_files` now uses `git ls-files` for git repositories, respecting `.gitignore` instead of a hardcoded extension whitelist. Non-git directories fall back to a directory-blacklist scan with binary-extension filtering.
- `Dockerfile`, `Makefile`, shell scripts, and other extension-less files are now visible to agents.

## [0.1.0] - 2026-07-25

### Added
- Multi-Agent Architecture Panel Chat application built on PydanticAI V2.
- Interactive Typer CLI with console interface supported by Rich panels and spinners.
- Reusable `codebase_inspector` capability for safe local file reading and listing.
- Specialized architect sub-agents (`db_expert`, `api_expert`, `clean_code_expert`) and automated delegation tool under `moderator` agent.
- Unit testing configuration using pytest for capabilities scanning.
