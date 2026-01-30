"""Base types for verifiers."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class VerificationResult:
    """Result of a verification check."""
    passed: bool
    message: str
    details: Dict[str, Any]
