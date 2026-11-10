"""GPU assignment fixtures shared by browser and browser-free Perchance checks."""
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def simulated_eight_gb_gpu():
    # Setup/provider paths look up inventory dynamically; Overview preflight
    # keeps a module-local import. Both must be simulated on GPU-less CI hosts.
    gpu = {'name': 'TEST GPU', 'total_gib': 8}
    with patch('workbench.inventory.detect_gpus', return_value=[gpu]), \
         patch('workbench.preflight.detect_gpus', return_value=[gpu]):
        yield
