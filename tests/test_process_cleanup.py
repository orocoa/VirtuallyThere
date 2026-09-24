import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from vt.pipeline import _worker

class ProcessCleanupTests(unittest.TestCase):
    def test_timeout_cleans_child_even_if_worker_exits_promptly(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);script=d/'worker.py'
            script.write_text('import subprocess,time\nfrom pathlib import Path\np=subprocess.Popen(["/bin/sleep","30"])\nPath('+repr(str(d/'child.pid'))+').write_text(str(p.pid))\ntime.sleep(30)\n')
            with self.assertRaises(ValueError):_worker([sys.executable,str(script)],d,.4)
            pid=int((d/'child.pid').read_text())
            for _ in range(20):
                status=subprocess.run(['/bin/ps','-p',str(pid),'-o','stat='],capture_output=True,text=True).stdout.strip()
                if not status or status.startswith('Z'):break
                time.sleep(.05)
            self.assertTrue(not status or status.startswith('Z'),status)

if __name__=='__main__':unittest.main()
