"""
Thread worker abstractions for PySide6 using QRunnable and QThreadPool.
Ensures zero UI freezing on the 7" 60 FPS Raspberry Pi display.
"""

import sys
import traceback
from typing import Callable, Any
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    """Signals available from a running worker thread."""
    started = Signal()
    finished = Signal()
    error = Signal(tuple)        # (exctype, value, traceback.format_exc())
    result = Signal(object)      # result object
    progress = Signal(int)       # progress percentage (0..100)


class BaseWorker(QRunnable):
    """Worker thread that executes a target function with arbitrary arguments."""

    def __init__(self, fn: Callable, *args: Any, **kwargs: Any):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        """Execute the function in a background thread."""
        self.signals.started.emit()
        try:
            res = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(res)
        finally:
            self.signals.finished.emit()
