# Security Review: Application Tools

## Summary

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🟠 HIGH | `packages/tools/applications/application_registry.py`, `packages/tools/applications/application_launcher.py` | `application_registry.py:42-49`; `application_launcher.py:50-83,116` | VS Code accepts unrestricted arguments, including `--extensionDevelopmentPath`, which can load and execute an untrusted extension while risk is determined only by the application name. | 8/10 |

## Finding 1: Unrestricted VS Code arguments can load executable extensions

**Severity:** High  
**Confidence:** 8/10

The VS Code entry in the application registry allows arguments, and the launcher passes caller-supplied arguments directly to the executable. An attacker who can influence a tool call and has a malicious extension directory available can use VS Code's `--extensionDevelopmentPath` option to launch an Extension Development Host and execute that extension as the agent's user.

The application risk lookup considers only the selected application name. Consequently, this argument-bearing VS Code launch remains medium risk and does not require approval under the current policy. Using `shell=False` prevents shell interpretation but does not prevent application-specific option injection.

**Recommended remediation:**

- Restrict VS Code arguments to narrowly allowlisted, non-code-loading options and reject `--extensionDevelopmentPath` and other execution/loading flags.
- Consider requiring approval for any launch with arguments.
- Keep risk evaluation aware of arguments where arguments can materially increase launch risk.

## Scope and limitations

This review covered the application registry, launcher, and tool implementation, with surrounding gateway policy consulted to assess authorization impact. No files were modified as part of the review; this report records the finding and its recommended remediation.
