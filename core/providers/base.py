from abc import ABC, abstractmethod

class DecisionProvider(ABC):
    @abstractmethod
    def ask(self, state, questions, key, model, timeout, base_url=None):
        """Return normalized answers and usage, or raise JevError."""

    @abstractmethod
    def list_models(self, key, timeout, base_url=None):
        """Return available model ids, or raise JevError."""
