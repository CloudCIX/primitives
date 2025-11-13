#!/usr/bin/env python3

import json
import sys

from cloudcix_primitives import project_lxd


def usage():
    print("usage:")
    print("  test_project_lxd.py build <name> <host> [verify_lxd_certs]")
    print("  test_project_lxd.py read  <name> <host> [verify_lxd_certs]")
    print("  test_project_lxd.py scrub <name> <host> [verify_lxd_certs]")
    print()
    print("examples:")
    print("  test_project_lxd.py build myproject https://127.0.0.1:8443 false")
    print("  test_project_lxd.py read  myproject https://127.0.0.1:8443 false")
    print("  test_project_lxd.py scrub myproject https://127.0.0.1:8443 false")


def to_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in ("build", "read", "scrub"):
        usage()
        sys.exit(1)

    # Defaults
    name = None
    host = None
    verify_lxd_certs = False

    # Parse required args
    if len(sys.argv) > 2:
        name = sys.argv[2]
    if len(sys.argv) > 3:
        host = sys.argv[3]
    if len(sys.argv) > 4:
        verify_lxd_certs = to_bool(sys.argv[4], False)

    if not name or not host:
        print('Name and host are required as the second and third arguments.')
        usage()
        sys.exit(3)

    status = None
    msg = None
    data = None

    if cmd == "build":
        status, msg = project_lxd.build(
            name=name,
            host=host,
            verify_lxd_certs=verify_lxd_certs,
        )
    elif cmd == "read":
        status, data, msg = project_lxd.read(
            name=name,
            host=host,
            verify_lxd_certs=verify_lxd_certs,
        )
    elif cmd == "scrub":
        status, msg = project_lxd.scrub(
            name=name,
            host=host,
            verify_lxd_certs=verify_lxd_certs,
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