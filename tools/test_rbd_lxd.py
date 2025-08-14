#!/usr/bin/env python3

import sys
import json
from cloudcix_primitives import rbd_lxd

def usage():
    print("usage:")
    print("  test_rbd_lxd.py build <endpoint_url> <project> <pool_name> <volume_name> <size_gb> [verify_lxd_certs]")
    print("  test_rbd_lxd.py read  <endpoint_url> <project> <pool_name> <volume_name> [verify_lxd_certs]")
    print("  test_rbd_lxd.py scrub <endpoint_url> <project> <pool_name> <volume_name> [verify_lxd_certs]")
    print("  test_rbd_lxd.py update <endpoint_url> <project> <pool_name> <volume_name> <size_gb> [verify_lxd_certs]")
    print()
    print("examples:")
    print("  test_rbd_lxd.py build https://127.0.0.1:8443 myproject rbd testvol 10 false")
    print("  test_rbd_lxd.py read  https://127.0.0.1:8443 myproject rbd testvol false")
    print("  test_rbd_lxd.py update https://127.0.0.1:8443 myproject rbd testvol 20 false")
    print("  test_rbd_lxd.py scrub https://127.0.0.1:8443 myproject rbd testvol false")

def to_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd not in ("build", "read", "scrub", "update"):
        usage()
        sys.exit(1)

    # Defaults
    endpoint_url = None
    project = None
    pool_name = "rbd"
    volume_name = "testvol"
    size_gb = 10
    verify_lxd_certs = False

    # Parse required args
    if len(sys.argv) > 2:
        endpoint_url = sys.argv[2]
    if len(sys.argv) > 3:
        project = sys.argv[3]
    if len(sys.argv) > 4:
        pool_name = sys.argv[4]
    if len(sys.argv) > 5:
        volume_name = sys.argv[5]

    # Size and verify flag depending on command
    if cmd in ("build", "update"):
        if len(sys.argv) > 6:
            try:
                size_gb = int(sys.argv[6])
            except Exception:
                print("Invalid size_gb, must be integer")
                sys.exit(2)
        if len(sys.argv) > 7:
            verify_lxd_certs = to_bool(sys.argv[7], False)
    else:
        if len(sys.argv) > 6:
            verify_lxd_certs = to_bool(sys.argv[6], False)

    if not endpoint_url or not project:
        print('Endpoint URL and project are required as the second and third arguments.')
        usage()
        sys.exit(3)

    status = None
    msg = None
    data = None

    if cmd == "build":
        status, msg = rbd_lxd.build(
            endpoint_url,
            project,
            pool_name,
            volume_name,
            size_gb,
            verify_lxd_certs,
        )
    elif cmd == "read":
        status, data, msg = rbd_lxd.read(
            endpoint_url,
            project,
            pool_name,
            volume_name,
            verify_lxd_certs,
        )
    elif cmd == "scrub":
        status, msg = rbd_lxd.scrub(
            endpoint_url,
            project,
            pool_name,
            volume_name,
            verify_lxd_certs,
        )
    elif cmd == "update":
        status, msg = rbd_lxd.update(
            endpoint_url,
            project,
            pool_name,
            volume_name,
            size_gb,
            verify_lxd_certs,
        )
    else:
        usage()
        sys.exit(4)

    print(f"Status: {status}")
    print()
    print("Message:")
    if isinstance(msg, list):
        for m in msg:
            print(m)
    else:
        print(msg if msg is not None else "")

    if data is not None:
        print()
        print("Data:")
        try:
            print(json.dumps(data, indent=2, sort_keys=True))
        except Exception:
            print(str(data))

if __name__ == "__main__":
    main()
