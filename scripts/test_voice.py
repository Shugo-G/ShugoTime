# -*- coding: utf-8 -*-
import os
import sys
import time

CWD = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.dirname(CWD)
sys.path.append(ROOT_DIR)

from zk import ZK


conn = None
zk = ZK('192.168.0.23', port=4370, timeout=5, password=0, force_udp=False, ommit_ping=False)
try:
    conn = zk.connect()
    for i in range(0, 55):
        print ("Voice number #%d" % i)
        conn.test_voice(i)
        time.sleep(3)
except Exception as e:
    print ("Process terminate : {}".format(e))
finally:
    if conn:
        conn.disconnect()