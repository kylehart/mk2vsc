"""
Experimental: assistant (ESS) injection by file.

Nothing in this package has produced a running ESS system.  It is published so the work can be picked
up, reviewed, or corrected.  Read docs/ESS_INJECTION.md first.  The CLI exposes these only behind
``mk2vsc experimental ... --i-accept-the-risk``.
"""
from .ess_graft import graft, GraftRefused, INSTALL_STATE

__all__ = ["graft", "GraftRefused", "INSTALL_STATE"]
