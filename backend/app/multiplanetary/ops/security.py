"""Cybersecurity layer for autonomous space systems.

Protects command and control (C2) uplink integrity, detects anomalous
traffic patterns, enforces anti-replay, and validates configuration
integrity.  Operational on both the spacecraft and the ground segment.
"""

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SecurityLevel(Enum):
    NOMINAL = "nominal"
    ADVISORY = "advisory"
    ALERT = "alert"
    LOCKDOWN = "lockdown"


class ThreatType(Enum):
    SPOOFED_COMMAND = "spoofed_command"
    REPLAY_ATTACK = "replay_attack"
    ANOMALOUS_VOLUME = "anomalous_volume"
    CONFIG_TAMPER = "config_tamper"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


@dataclass
class SecurityEvent:
    timestamp: float
    threat: ThreatType
    severity: str
    description: str
    source_ip: Optional[str] = None
    mitigated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "threat": self.threat.value,
            "severity": self.severity,
            "description": self.description,
            "mitigated": self.mitigated,
        }


class CyberSecurityLayer:
    def __init__(
        self,
        secret_key: bytes = b"default-key-change-me",
        rate_limit_per_minute: int = 60,
    ):
        self._secret_key = secret_key
        self._level = SecurityLevel.NOMINAL
        self._events: List[SecurityEvent] = []
        self._nonce_window: Dict[str, float] = {}
        self._command_history: List[Dict[str, Any]] = []
        self._max_command_history: int = 1000
        self._rate_limit_per_minute = rate_limit_per_minute
        self._config_hashes: Dict[str, str] = {}
        self._blocked_sources: set = set()

    def sign_command(self, command_id: str, payload: bytes, timestamp: float) -> str:
        message = f"{command_id}:{timestamp}:{payload.hex()}".encode()
        return hmac.new(self._secret_key, message, hashlib.sha256).hexdigest()

    def verify_command(
        self, command_id: str, payload: bytes, timestamp: float,
        signature: str, source_ip: Optional[str] = None,
    ) -> bool:
        if source_ip and source_ip in self._blocked_sources:
            self._log_event(SecurityEvent(
                timestamp=timestamp,
                threat=ThreatType.UNAUTHORIZED_ACCESS,
                severity="critical",
                description=f"Blocked command from {source_ip}.",
                source_ip=source_ip,
            ))
            return False
        expected = self.sign_command(command_id, payload, timestamp)
        if not hmac.compare_digest(expected, signature):
            self._log_event(SecurityEvent(
                timestamp=timestamp,
                threat=ThreatType.SPOOFED_COMMAND,
                severity="critical",
                description=f"Invalid signature on command {command_id}.",
                source_ip=source_ip,
                mitigated=True,
            ))
            return False
        nonce_key = f"{command_id}:{signature[:8]}"
        if nonce_key in self._nonce_window:
            self._log_event(SecurityEvent(
                timestamp=timestamp,
                threat=ThreatType.REPLAY_ATTACK,
                severity="alert",
                description=f"Replay detected for command {command_id}.",
                mitigated=True,
            ))
            return False
        self._nonce_window[nonce_key] = timestamp
        self._cleanup_nonces(timestamp)
        self._check_rate_limit(timestamp, source_ip)
        self._command_history.append({"id": command_id, "timestamp": timestamp})
        if len(self._command_history) > self._max_command_history:
            self._command_history = self._command_history[-self._max_command_history:]
        return True

    def register_config_hash(self, config_id: str, content: bytes) -> None:
        self._config_hashes[config_id] = hashlib.sha256(content).hexdigest()

    def verify_config(self, config_id: str, content: bytes) -> bool:
        expected = self._config_hashes.get(config_id)
        if expected is None:
            return True
        actual = hashlib.sha256(content).hexdigest()
        if expected != actual:
            self._log_event(SecurityEvent(
                timestamp=0.0,
                threat=ThreatType.CONFIG_TAMPER,
                severity="critical",
                description=f"Configuration {config_id} integrity check failed.",
                mitigated=True,
            ))
            return False
        return True

    def _cleanup_nonces(self, now: float) -> None:
        self._nonce_window = {
            k: v for k, v in self._nonce_window.items() if now - v < 3600
        }

    def _check_rate_limit(self, timestamp: float, source_ip: Optional[str]) -> None:
        recent = [c for c in self._command_history if timestamp - c["timestamp"] < 60]
        if len(recent) > self._rate_limit_per_minute:
            self._log_event(SecurityEvent(
                timestamp=timestamp,
                threat=ThreatType.ANOMALOUS_VOLUME,
                severity="alert",
                description=f"Command volume exceeded rate limit ({len(recent)} in 60s).",
                source_ip=source_ip,
            ))

    def _log_event(self, event: SecurityEvent) -> None:
        self._events.append(event)
        if len(self._events) > 500:
            self._events = self._events[-500:]

    @property
    def level(self) -> SecurityLevel:
        return self._level

    @property
    def events(self) -> List[SecurityEvent]:
        return list(self._events)

    @property
    def recent_events(self) -> List[SecurityEvent]:
        return self._events[-10:]