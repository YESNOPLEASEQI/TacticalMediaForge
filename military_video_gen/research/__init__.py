"""Evidence-grounded military storyboard research."""

from .freshness import compute_input_hash
from .models import ResearchRequest, ResearchSnapshot

__all__ = ["ResearchRequest", "ResearchSnapshot", "compute_input_hash"]
