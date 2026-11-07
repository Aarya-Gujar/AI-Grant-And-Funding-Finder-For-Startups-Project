"""
app/services/__init__.py — service layer exports
"""
from .granite_service import GraniteAIService
from .grant_aggregator import GrantAggregator
from .matching_engine import MatchingEngine
from .proposal_generator import ProposalGenerator

__all__ = ["GraniteAIService", "GrantAggregator", "MatchingEngine", "ProposalGenerator"]
