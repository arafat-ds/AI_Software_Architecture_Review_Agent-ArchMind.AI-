# Injection Prevention Patterns

## SQL Injection Prevention

SQL injection occurs when user-supplied input is incorporated into SQL query strings
without proper parameterisation, allowing attackers to manipulate query structure.

### Parameterised Queries

Always use parameterised queries (prepared statements) instead of string concatenation.
The database driver separates query structure from data values — user input can never
alter query syntax.

```
SAFE:   cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
UNSAFE: cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### ORM Usage

Object-Relational Mappers parameterise queries by default. Use ORM query builders
rather than raw SQL strings. Avoid ORM "raw query" escape hatches unless strictly
necessary; treat them with the same rigour as raw SQL.

### Input Validation

Validate and type-coerce user input at system entry points before it reaches query
construction code. For numeric IDs: parse to integer and reject non-numeric input.
For strings: apply length limits and character whitelists where applicable.

### Stored Procedures

Stored procedures that concatenate input internally are still vulnerable. Only
use stored procedures with parameterised inputs.

## OS Command Injection Prevention

Command injection occurs when user-supplied data is incorporated into shell commands
executed by the application server.

### Avoid Shell Execution

Never pass user input to shell=True subprocess calls. Use subprocess with a list
of arguments — argument list form never invokes a shell interpreter.

```
SAFE:   subprocess.run(["git", "clone", repo_url], check=True)
UNSAFE: subprocess.run(f"git clone {repo_url}", shell=True)
```

### Input Validation for System Operations

Whitelist allowed characters for any value that will be used in a system operation.
Repository URLs: validate against a strict URL format before use.
File paths: resolve to absolute paths and validate against an allowed root directory
(path traversal prevention).

### Avoid eval() and exec()

Never pass user-controlled content to eval(), exec(), or compile(). There is no safe
way to sanitise input for dynamic code execution. Refactor to achieve the goal without
dynamic code evaluation.

## Template Injection Prevention

Server-Side Template Injection (SSTI) occurs when user input is rendered as part of a
template expression rather than as a literal value.

### Escape All User Input

Template engines provide escaping functions that render values as literal text.
Never disable auto-escaping for user-controlled values. Do not use template engines
to render user-supplied content as template source.

### Separate Templates from Data

Template source code must be authored by trusted developers only. User-supplied data
is passed to templates as context variables, never as template fragments.

### Jinja2 Specific

Use the Jinja2 sandbox environment for any template rendering that incorporates
user-provided values. Never use `jinja2.Environment(undefined=Undefined)` with
user-provided templates.

## LDAP Injection Prevention

Escape all special LDAP characters in user-supplied values: `* ( ) \ NUL / `.
Use an LDAP library that provides parameterised query support.
Validate and whitelist all values used in LDAP filter construction.

## XML Injection Prevention

Disable external entity processing (XXE) in XML parsers:
- Set `resolve_entities=False` in lxml.
- Disable DOCTYPE processing for untrusted XML inputs.
- Use defusedxml library for parsing untrusted XML in Python.

## General Injection Defence

1. Parameterise all interpreter calls — SQL, LDAP, OS, template, XPath.
2. Validate at entry points — type coercion before use, whitelist over blacklist.
3. Least privilege — database accounts should have only the permissions required.
4. Defence in depth — WAF rules as a secondary layer, not the primary defence.
