"""Deep-space telemetry and store-and-forward relay.

Models the comms delay challenge: telemetry is stored locally and
downlinked when a ground station is visible.  For deep-space missions,
relay satellites (like Mars Reconnaissance Orbiter) provide store-and-forward.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class RelayMode(Enum):
    DIRECT_TO_EARTH = "direct_to_earth"
    ORBITAL_RELAY = "orbital_relay"
    STORE_AND_FORWARD = "store_and_forward"


@dataclass
class TelemetryPacket:
    source: str
    timestamp: float
    data: Dict[str, Any]
    priority: int = 0
    size_bytes: int = 0
    attempts: int = 0
    relay_path: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "data": self.data,
            "priority": self.priority,
            "size_bytes": self.size_bytes,
            "attempts": self.attempts,
            "relay_path": self.relay_path,
        }


@dataclass
class LinkState:
    distance_au: float = 0.01
    one_way_delay_s: float = 0.0
    data_rate_bps: int = 9600
    snr_db: float = 20.0
    available: bool = True

    @property
    def round_trip_delay_s(self) -> float:
        return self.one_way_delay_s * 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "distance_au": round(self.distance_au, 4),
            "one_way_delay_s": round(self.one_way_delay_s, 2),
            "data_rate_bps": self.data_rate_bps,
            "available": self.available,
        }


class StoreAndForwardRelay:
    """Store-and-forward relay for deep-space communications.

    Packets are stored locally with priority ordering and transmitted
    when a link becomes available.
    """

    def __init__(self, storage_capacity_packets: int = 5000, relay_mode: RelayMode = RelayMode.STORE_AND_FORWARD):
        self.storage_capacity = storage_capacity_packets
        self.relay_mode = relay_mode
        self._storage: List[TelemetryPacket] = []
        self._transmitted: List[TelemetryPacket] = []
        self._dropped: int = 0
        self._total_bytes_stored = 0
        self._total_bytes_transmitted = 0

    def store(self, packet: TelemetryPacket) -> bool:
        if len(self._storage) >= self.storage_capacity:
            self._dropped += 1
            return False
        self._storage.append(packet)
        self._total_bytes_stored += packet.size_bytes
        return True

    def transmit_batch(self, max_bytes: int, link: LinkState) -> List[TelemetryPacket]:
        if not link.available:
            return []
        transmitted: List[TelemetryPacket] = []
        remaining = max_bytes
        self._storage.sort(key=lambda p: -p.priority)
        while self._storage and remaining > 0:
            pkt = self._storage[0]
            if pkt.size_bytes <= remaining:
                self._storage.pop(0)
                pkt.attempts += 1
                pkt.relay_path.append("relay")
                transmitted.append(pkt)
                remaining -= pkt.size_bytes
                self._total_bytes_transmitted += pkt.size_bytes
            else:
                break
        self._transmitted.extend(transmitted)
        return transmitted

    @property
    def storage_depth(self) -> int:
        return len(self._storage)

    @property
    def total_transmitted(self) -> int:
        return len(self._transmitted)

    @property
    def total_dropped(self) -> int:
        return self._dropped

    def flush(self) -> None:
        self._storage.clear()


class DeepSpaceTelemetry:
    """Top-level telemetry manager for deep-space missions.

    Handles packetization, compression estimation, priority queuing,
    and relay scheduling.
    """

    def __init__(self, relay: Optional[StoreAndForwardRelay] = None):
        self.relay = relay or StoreAndForwardRelay()
        self._packet_counter = 0
        self._link_state = LinkState()

    def set_link_state(self, link_state: LinkState) -> None:
        self._link_state = link_state

    def send(self, source: str, data: Dict[str, Any], priority: int = 0) -> TelemetryPacket:
        self._packet_counter += 1
        pkt = TelemetryPacket(
            source=source,
            timestamp=time.time(),
            data=data,
            priority=priority,
            size_bytes=len(str(data)) + 32,
        )
        self.relay.store(pkt)
        return pkt

    def transmit_available(self, contact_s: float = 300.0) -> List[TelemetryPacket]:
        max_bytes = int(contact_s * self._link_state.data_rate_bps / 8)
        return self.relay.transmit_batch(max_bytes, self._link_state)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "packets_sent": self._packet_counter,
            "storage_depth": self.relay.storage_depth,
            "total_transmitted": self.relay.total_transmitted,
            "total_dropped": self.relay.total_dropped,
            "link": self._link_state.to_dict(),
        }