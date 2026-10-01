from abc import ABC, abstractmethod
from typing import Callable


class WakeWordProvider(ABC):

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the wake-word engine."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start listening for the wake word."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop listening."""
        pass

    @abstractmethod
    def on_detected(self, callback: Callable[[str], None]) -> None:
        """Register a callback for wake-word detection."""
        pass

    @abstractmethod
    def destroy(self) -> None:
        """Release resources."""
        pass