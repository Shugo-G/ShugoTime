import os
import sys
from zk.exception import ZKErrorConnection

CWD = os.path.dirname(os.path.realpath(__file__))
ROOT_DIR = os.path.dirname(CWD)
sys.path.append(ROOT_DIR)

from zk import ZK, const

conn = None
zk = ZK('192.168.0.23', port=4370, timeout=5, password=0, force_udp=False, ommit_ping=False, verbose=True)
try:
    conn = zk.connect()
    print("Conectado al reloj")
    print("Enviando restart...")
    #conn.poweroff()
    conn.restart()
    print("Comando enviado")
except Exception as e:
    print ("Process terminate : {}".format(e))
    print(f"Error: {e}")
finally:
    if conn:
        try:
            conn.disconnect()
        except ZKErrorConnection:
            pass