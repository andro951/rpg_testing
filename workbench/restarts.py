"""Resume an explicitly requested Run after a source-update restart; no test tracker."""
from __future__ import annotations
import threading
import time
from .domain import read_json,write_json

MAX_AUTOMATIC_RESTARTS=3
REQUEST_TTL_SECONDS=600


def consume_request(app,clock=time.time):
    path=app.data/'resume-after-update.json'
    if not path.exists():return False
    try:
        request=read_json(path)
        age=clock()-request['created_at']
        count=request['restart_count']
        valid=(request.get('operation')=='run' and type(count)is int and 1<=count<=MAX_AUTOMATIC_RESTARTS
               and 0<=age<=REQUEST_TTL_SECONDS)
    except (ValueError,KeyError,TypeError):valid=False
    path.unlink()
    if not valid:
        app.log('restart','Ignored stale or invalid restart intent. No experiment was started.')
        return False
    app.automatic_restart_count=count
    return True


class UpdateCoordinator:
    def __init__(self,server,interval=.1):
        self.server=server;self.app=server.app;self.interval=interval
        self.stop=threading.Event();self.thread=None
    def start(self):
        resume=consume_request(self.app)
        def watch():
            while not self.stop.wait(self.interval):
                if not self.app.restart_required or self.app.operation.locked():continue
                if self.app.cancel_event.is_set():return
                count=getattr(self.app,'automatic_restart_count',0)+1
                if count>MAX_AUTOMATIC_RESTARTS:
                    self.app.state='error';self.app.message='Source changed repeatedly; automatic restarts stopped safely. No model was left running.'
                    self.app.log('restart',self.app.message);self.app.flush_logs();return
                write_json(self.app.data/'resume-after-update.json',
                           {'operation':'run','created_at':time.time(),'restart_count':count})
                self.app.log('restart','Restarting on the new source and resuming the requested Run automatically.')
                self.app.flush_logs();self.server.exit_requested=True
                self.server.close_all();return
        self.thread=threading.Thread(target=watch,name='source-update-coordinator',daemon=True);self.thread.start()
        if resume:
            self.app.log('restart','Continuing the requested Run after source update.')
            self.app.start('run')
        return self
