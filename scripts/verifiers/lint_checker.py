"""Verify lint clean claims by running linters."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .base import VerificationResult


def detect_lint_command(cwd: str) -> Optional[Tuple[str, str]]:
    """
    Detect the appropriate lint command for the project.

    Args:
        cwd: Current working directory

    Returns:
        Tuple of (command, linter_name) or None if not detected
    """
    # Node.js/npm projects
    pkg_json = os.path.join(cwd, "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, 'r') as f:
                pkg = json.load(f)
            scripts = pkg.get("scripts", {})
            if "lint" in scripts:
                return ("npm run lint", "npm")
            # Check for eslint config
            if os.path.exists(os.path.join(cwd, ".eslintrc.js")) or \
               os.path.exists(os.path.join(cwd, ".eslintrc.json")) or \
               os.path.exists(os.path.join(cwd, "eslint.config.js")):
                return ("npx eslint .", "eslint")
        except (json.JSONDecodeError, IOError):
            pass

    # Python projects with ruff
    if os.path.exists(os.path.join(cwd, "ruff.toml")) or \
       os.path.exists(os.path.join(cwd, ".ruff.toml")):
        return ("ruff check .", "ruff")

    # Python projects - check pyproject.toml for tools
    pyproject = os.path.join(cwd, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            with open(pyproject, 'r') as f:
                content = f.read()
            if "[tool.ruff" in content:
                return ("ruff check .", "ruff")
            if "[tool.flake8" in content or "[tool.pylint" in content:
                return ("flake8 .", "flake8")
        except IOError:
            pass

    # Python with pylint or flake8 config
    if os.path.exists(os.path.join(cwd, ".pylintrc")):
        return ("pylint **/*.py", "pylint")
    if os.path.exists(os.path.join(cwd, ".flake8")):
        return ("flake8", "flake8")

    # Rust projects
    if os.path.exists(os.path.join(cwd, "Cargo.toml")):
        return ("cargo clippy -- -D warnings", "clippy")

    # Go projects
    if os.path.exists(os.path.join(cwd, "go.mod")):
        return ("golangci-lint run", "golangci-lint")

    return None


def verify_lint_clean(claim_value: Optional[str], cwd: str,
                      config: Dict[str, Any]) -> VerificationResult:
    """
    Verify that linting passes with no errors.

    Args:
        claim_value: Not used for lint verification
        cwd: Current working directory
        config: Verifier configuration

    Returns:
        VerificationResult indicating if lint passes
    """
    timeout = config.get("timeout", 30)
    custom_command = config.get("command")

    # Use custom command if specified
    if custom_command:
        lint_command = custom_command
        linter = "custom"
    else:
        # Auto-detect lint command
        detected = detect_lint_command(cwd)
        if detected is None:
            return VerificationResult(
                passed=True,
                message="No linter detected, skipping verification",
                details={"skipped": True, "reason": "no_linter"}
            )
        lint_command, linter = detected

    try:
        result = subprocess.run(
            lint_command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode == 0:
            return VerificationResult(
                passed=True,
                message=f"Lint passed ({linter})",
                details={
                    "command": lint_command,
                    "linter": linter,
                    "exit_code": result.returncode
                }
            )
        else:
            # Extract lint errors
            output = result.stdout + result.stderr
            output_tail = output[-1000:] if output else "No output"

            return VerificationResult(
                passed=False,
                message=f"Lint errors found ({linter})",
                details={
                    "command": lint_command,
                    "linter": linter,
                    "exit_code": result.returncode,
                    "output_tail": output_tail
                }
            )

    except subprocess.TimeoutExpired:
        return VerificationResult(
            passed=False,
            message=f"Lint check timed out after {timeout}s",
            details={
                "command": lint_command,
                "linter": linter,
                "timeout": timeout,
                "error": "timeout"
            }
        )
    except Exception as e:
        return VerificationResult(
            passed=False,
            message=f"Failed to run linter: {str(e)}",
            details={
                "command": lint_command,
                "linter": linter,
                "error": str(e)
            }
        )
