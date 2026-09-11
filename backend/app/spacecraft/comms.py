"""Communications subsystem for CubeSat.

Models: UHF/VHF radio transceiver, AX.25 packet framing, link budget,
and store-and-forward for deep-space relay.  The same interface works
for LEO (direct ground contact) and deep-space (DTN/store-and-forward)
modes.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommsMode(Enum):
    OFF = "off"
    RECEIVE = "receive"
    TRANSMIT = "transmit"
    FULL_DUPLEX = "full_duplex"
    STORE_AND_FORWARD = "store_and_forward"


@dataclass
class Packet:
    source: str
    dest: str
    payload: bytes
    seq: int = 0
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_bytes(self) -> int:
        return len(self.payload) + 16  # AX.25 header overhead

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "dest": self.dest,
            "size_bytes": self.size_bytes,
            "seq": self.seq,
            "timestamp": self.timestamp,
        }


class LinkBudget:
    """Simplified link budget calculator.

    Uses free-space path loss only (no atmospheric, rain, or multipath).
    """

    def __init__(
        self,
        frequency_mhz: float = 435.0,
        tx_power_dbm: float = 30.0,
        tx_gain_dbi: float = 0.0,
        rx_gain_dbi: float = 0.0,
        system_noise_figure_db: float = 3.0,
    ):
        self.frequency_ghz = frequency_mhz / 1000.0
        self.tx_power_dbm = tx_power_dbm
        self.tx_gain_dbi = tx_gain_dbi
        self.rx_gain_dbi = rx_gain_dbi
        self.system_noise_figure_db = system_noise_figure_db

    def free_space_path_loss_db(self, distance_km: float) -> float:
        if distance_km <= 0:
            return 0.0
        return 20 * math.log10(distance_km) + 20 * math.log10(self.frequency_ghz) + 32.45

    def received_power_dbm(self, distance_km: float) -> float:
        fspl = self.free_space_path_loss_db(distance_km)
        return self.tx_power_dbm + self.tx_gain_dbi + self.rx_gain_dbi - fspl

    def snr_db(self, distance_km: float) -> float:
        rx = self.received_power_dbm(distance_km)
        noise_dbm = -174 + 10 * math.log10(9600) + self.system_noise_figure_db
        return rx - noise_dbm

    def max_range_km(self, min_snr_db: float = 10.0) -> float:
        noise_dbm = -174 + 10 * math.log10(9600) + self.system_noise_figure_db
        max_rx = noise_dbm + min_snr_db
        max_fspl = self.tx_power_dbm + self.tx_gain_dbi + self.rx_gain_dbi - max_rx
        if max_fspl <= 0:
            return 1e6
        freq_ghz = self.frequency_ghz
        dist_km = 10 ** ((max_fspl - 20 * math.log10(freq_ghz) - 32.45) / 20)
        return dist_km


class RadioTransceiver:
    def __init__(
        self,
        frequency_mhz: float = 435.0,
        data_rate_bps: int = 9600,
        max_packet_bytes: int = 256,
        tx_power_dbm: float = 30.0,
        is_simulated: bool = True,
    ):
        self.frequency_mhz = frequency_mhz
        self.data_rate_bps = data_rate_bps
        self.max_packet_bytes = max_packet_bytes
        self.link = LinkBudget(frequency_mhz=frequency_mhz, tx_power_dbm=tx_power_dbm)
        self.mode = CommsMode.OFF
        self.is_simulated = is_simulated
        self._tx_buffer: list[Packet] = []
        self._rx_buffer: list[Packet] = []
        self._store_forward: list[Packet] = []
        self._packets_tx = 0
        self._packets_rx = 0
        self._bytes_tx = 0
        self._seq = 0

    def turn_on(self) -> None:
        self.mode = CommsMode.RECEIVE

    def turn_off(self) -> None:
        self.mode = CommsMode.OFF

    def queue_packet(self, packet: Packet) -> None:
        packet.seq = self._seq
        self._seq += 1
        self._tx_buffer.append(packet)

    def transmit(self, distance_km: float) -> list[Packet]:
        if self.mode == CommsMode.OFF:
            return []
        sent = []
        for pkt in list(self._tx_buffer):
            if self.link.snr_db(distance_km) > 5.0:
                sent.append(pkt)
                self._packets_tx += 1
                self._bytes_tx += pkt.size_bytes
            else:
                if self.mode == CommsMode.STORE_AND_FORWARD:
                    self._store_forward.append(pkt)
        self._tx_buffer = [p for p in self._tx_buffer if p not in sent]
        return sent

    def receive(self, packets: list[Packet]) -> None:
        self._rx_buffer.extend(packets)
        self._packets_rx += len(packets)

    @property
    def stats(self) -> dict[str, int]:
        return {
            "packets_tx": self._packets_tx,
            "packets_rx": self._packets_rx,
            "bytes_tx": self._bytes_tx,
            "tx_queue": len(self._tx_buffer),
            "rx_queue": len(self._rx_buffer),
            "store_forward_queue": len(self._store_forward),
        }


class GroundStation:
    """Simplified ground station model."""

    def __init__(self, name: str, latitude_deg: float, longitude_deg: float):
        self.name = name
        self.latitude_deg = latitude_deg
        self.longitude_deg = longitude_deg
        self.radio = RadioTransceiver(frequency_mhz=145.0, tx_power_dbm=40.0, is_simulated=True)
        self._contact_window_s: float = 0.0

    def set_contact_window(self, duration_s: float) -> None:
        self._contact_window_s = duration_s

    def slant_range_km(self, sat_alt_km: float, elevation_deg: float) -> float:
        r_earth = 6371.0
        r_sat = r_earth + sat_alt_km
        el_rad = math.radians(max(0.0, elevation_deg))
        slant = math.sqrt(r_earth**2 + r_sat**2 - 2 * r_earth * r_sat * math.cos(el_rad))
        return max(0.0, slant - r_earth)
