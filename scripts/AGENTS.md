# Scripts

Utility scripts for data loading and maintenance.

## Rules

- Scripts must be idempotent (safe to run multiple times)
- Scripts must validate data before inserting
- Scripts must log what they insert (record counts per table)
- Read database URL from .env via app/config.py — never hardcode
- Do not run scripts in the sandbox — the human runs them
