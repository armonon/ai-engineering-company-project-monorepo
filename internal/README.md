# `internal` folder

This folder contains **internal tools and utilities** built for the development team (for example: CLIs, packaged migration scripts, prompt evaluators, etc.).

Unlike simple scripts in `/scripts`, these are structured tools with their own dependencies, tests, and package configurations.

- **Main purpose**: to centralize robust utilities used internally by the engineering team.
- **Recommendation**: document how to install and use each internal tool.

## Tools

- [`todo-list-cli-python/`](./todo-list-cli-python/) — the standard-library
  operations task manager built on the official 4Geeks Python starter
  contract. It adds, lists, deletes, saves, and reloads pending tasks.

> _Spanish version: [README.es.md](./README.es.md)._
