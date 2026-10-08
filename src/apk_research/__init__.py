"""apk-research core package."""

__version__ = "0.30.1"

# v0.30.1 adds direct package TCP/443 routing through the local HTTPS analyzer
# so applications that ignore Android's system proxy can still be inspected.
# Stable release documentation is synchronized by the main release gate.
__all__ = ["__version__"]
