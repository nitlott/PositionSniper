#!/usr/bin/env python
from market_maker import market_maker
import logging
import sys
import os
pid = str(os.getpid())
pidfile = "run-lock.pid"

if os.path.isfile(pidfile):
    print("%s already exists, exiting" % pidfile)
    sys.exit()
with open(pidfile, 'w', encoding='utf-8') as f:
    f.write(str(os.getpid()))
try:
    def start():
        while True:
            try:
                market_maker.run()
            except (KeyboardInterrupt, SystemExit):
                sys.exit()
            time.sleep(15)


    start()
finally:
    os.unlink(pidfile)




