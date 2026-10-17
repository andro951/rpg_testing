"""Read-only, versioned diagnostics; never changes benchmark scoring or identity."""
from .core import assess, assess_record

__all__ = ['assess', 'assess_record']
