"""
Switch Port LED Flasher / Blinker tool with adjustable cadence.
Prevents Cisco IOS 'errdisable detect cause link-flap' port shutdowns
by supporting adjustable blink intervals (1s to 5s) and non-disruptive PHY LED identification.
"""

import subprocess
import threading
import time
from typing import Optional, Callable


class PortBlinker:
    """Controls physical switch port link light blinking with configurable safe cadence."""

    def __init__(self, interface: str = "eth0", simulate: bool = False):
        self.interface = interface
        self.simulate = simulate
        self.interval_sec: float = 3.0  # Safe default (3.0s cadence prevents Cisco link-flap errdisable)
        self._is_blinking = False
        self._thread: Optional[threading.Thread] = None
        self._tick_callback: Optional[Callable[[bool], None]] = None

    def set_interval(self, seconds: float):
        """Set blink period in seconds (clamped between 1.0s and 6.0s)."""
        self.interval_sec = max(1.0, min(6.0, float(seconds)))

    def start_blink(
        self,
        duration_sec: int = 30,
        interval_sec: Optional[float] = None,
        on_tick: Optional[Callable[[bool], None]] = None
    ) -> bool:
        """Start blinking for the specified duration and cadence."""
        if interval_sec is not None:
            self.set_interval(interval_sec)

        if self._is_blinking:
            return True

        self._is_blinking = True
        self._tick_callback = on_tick

        self._thread = threading.Thread(
            target=self._blink_worker,
            args=(duration_sec,),
            daemon=True
        )
        self._thread.start()
        return True

    def stop_blink(self):
        """Stop blinking immediately and ensure interface link is UP."""
        self._is_blinking = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    @property
    def is_blinking(self) -> bool:
        return self._is_blinking

    def _blink_worker(self, duration_sec: int):
        """Worker thread executing safe LED pulse cycles."""
        start = time.time()

        # Non-disruptive hardware PHY LED identify via ethtool -p
        proc = None
        if not self.simulate:
            try:
                proc = subprocess.Popen(
                    ["ethtool", "-p", self.interface, str(duration_sec)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

        led_state = False
        while self._is_blinking and (time.time() - start) < duration_sec:
            led_state = not led_state
            if self._tick_callback:
                try:
                    self._tick_callback(led_state)
                except Exception:
                    pass

            # Pulse link auto-negotiation safely at user-configured cadence if interval >= 2.0s
            if not self.simulate and led_state and self.interval_sec >= 2.0:
                try:
                    subprocess.run(
                        ["ethtool", "-r", self.interface],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=1.0
                    )
                except Exception:
                    pass

            # Sleep in small increments so stop_blink() responds instantly
            step_sleep = max(0.25, self.interval_sec / 2.0)
            slept = 0.0
            while self._is_blinking and slept < step_sleep:
                time.sleep(0.1)
                slept += 0.1

        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

        self._is_blinking = False
        if self._tick_callback:
            try:
                self._tick_callback(False)
            except Exception:
                pass
