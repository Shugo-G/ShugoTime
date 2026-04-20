# Clear attendances records
#conn.clear_attendance()

# -*- coding: utf-8 -*-
import os
import sys

CWD = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.dirname(CWD)
sys.path.append(ROOT_DIR)

from zk import ZK, const

conn = None
zk = ZK('192.168.0.22', port=4370, timeout=5, password=1884, force_udp=False, ommit_ping=False)
try:
    conn = zk.connect()
    #conn.enable_device()
    # Get attendances (will return list of Attendance object)
    attendances = conn.get_attendance()
    print(attendances)
except Exception as e:
    print ("Process terminate : {}".format(e))
finally:
    if conn:
        conn.disconnect()