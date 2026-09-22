"""Native-interface test double. Never evidence of model quality or GPU performance."""
import contextlib
from .backends import DemoBackend

class DemoNative(DemoBackend):
    def __init__(self,settings=None,gpu=None,log=lambda *a:None):super().__init__(log)
    def load(self,model,context,cancel=None,layers='all',execution_class='full_gpu'):
        super().load(model,context,cancel)
        self.load_metadata.update(placement={'status':execution_class,'gpu_layers':33 if layers=='all' else layers,
                                            'total_layers':33,'cpu_layers':0 if layers=='all' else 33-layers},
                                  execution_class=execution_class)
        return self.load_metadata
    @contextlib.contextmanager
    def budget(self,seconds,terminate_process=True):yield
