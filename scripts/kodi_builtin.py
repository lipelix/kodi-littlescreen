"""Run a Kodi built-in (e.g. UpdateLocalAddons) through the EventServer (UDP 9777).

JSON-RPC cannot run built-ins, the EventServer can. Usage: kodi_builtin.py HOST BUILTIN
"""

import socket
import struct
import sys
import time

PT_HELO, PT_BYE, PT_ACTION = 0x01, 0x02, 0x0A
ACTION_EXECBUILTIN = 0x01


def packet(ptype, payload, uid):
    header = b"XBMC" + struct.pack("!BBHIIHI", 2, 0, ptype, 1, 1, len(payload), uid) + b"\0" * 10
    return header + payload


def main():
    host, builtin = sys.argv[1], sys.argv[2]
    uid = int(time.time()) & 0xFFFFFFFF
    helo = b"kodi-ytkids\0" + bytes([0]) + struct.pack("!HII", 0, 0, 0)
    action = bytes([ACTION_EXECBUILTIN]) + builtin.encode() + b"\0"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for ptype, payload in ((PT_HELO, helo), (PT_ACTION, action), (PT_BYE, b"")):
            sock.sendto(packet(ptype, payload, uid), (host, 9777))
            time.sleep(0.2)


if __name__ == "__main__":
    main()
