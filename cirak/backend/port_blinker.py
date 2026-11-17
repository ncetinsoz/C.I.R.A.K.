"""
Switch Port LED Flasher / Blinker tool.
Blinks the physical Ethernet RJ45 port LED at 2 Hz to locate the cable
on dense patch panels and switch racks (wraps ethtool -p).
"""

import subprocess
import threading
import time
from typing import Optional, Callable


class PortBlinker:
    """Controls physical switch port link light blinking."""

    def __init__(self, interface: str = "eth0", simulate: bool = False):
        self.interface = interface
        self.simulate = simulate
        self._is_blinking = False
        self._thread: Optional[threading.Thread] = None
        self._tick_callback: Optional[Callable[[bool], None]] = None

    def start_blink(self, duration_sec: int = 15, on_tick: Optional[Callable[[bool], None]] = None) -> bool:
        """Start blinking for the specified duration in seconds."""
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
        """Stop blinking immediately."""
        self._is_blinking = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    @property
    def is_blinking(self) -> bool:
        return self._is_blinking

    def _blink_worker(self, duration_sec: int):
        """Worker thread executing LED pulse cycles."""
        start = time.time()

        # If on Linux with ethtool available, invoke ethtool -p in background
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
            time.sleep(0.5)  # 2 Hz frequency (0.5s on, 0.5s off)

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
