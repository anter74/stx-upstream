import datetime
import fnmatch
import os
import resource
import subprocess
from django.conf import settings


errorlog = "/var/log/horizon/gunicorn.log"
capture_output = True

# maxrss ceiling in kbytes
MAXRSS_CEILING = 512000


def worker_abort(worker):
    path = ("/proc/%s/fd") % os.getpid()
    contents = os.listdir(path)
    upload_dir = getattr(settings, 'FILE_UPLOAD_TEMP_DIR', '/tmp')
    pattern = os.path.join(upload_dir, '*.upload') 

    for i in contents:
        f = os.path.join(path, i)
        if os.path.exists(f):
            try:
                l = os.readlink(f)
                if fnmatch.fnmatch(l, pattern):
                    worker.log.info(l)
                    os.remove(l)
            except OSError:
                pass


def when_ready(server):
    subprocess.check_call(["/usr/bin/horizon-assets-compress"])


def post_worker_init(worker):
    worker.nrq = 0
    worker.restart = False


def pre_request(worker, req):
    worker.nrq += 1
    if worker.restart:
        worker.nr = worker.max_requests - 1
        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        msg = "%(date)s %(uri)s %(rss)u" % ({'date': datetime.datetime.now(),
                                             'uri': getattr(req, "uri"),
                                             'rss': maxrss})
        worker.log.info(msg)


def post_request(worker, req, environ, resp):
    worker.nrq -= 1
    if not worker.restart:
        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if maxrss > MAXRSS_CEILING and worker.nrq == 0:
            worker.restart = True
