#!/usr/bin/env python3
#MISE description="Install the basic commands every machine shares, which a bare Debian or Ubuntu lacks, through apt, such as `mise run basics`"
# Copyright © 2026 Ömer Göktaş. All Rights Reserved.

"""Gives a Linux machine the basic commands that Windows, with the global
file's niubash and BusyBox, and a fresh macOS both have, and that a bare
Debian or Ubuntu lacks, such as a fresh Docker image: one shell baseline on
every system. Its curl also brings libcurl.so.4, which the HTTPS helper of
the global git build loads on Linux.

The list holds the commands of the Windows setup that macOS also ships, with
Apple's command-line tools, which every developer on a Mac installs, less those
a bare Ubuntu already has; xz, for one, is missing from macOS, so it is not
here. A project's own mise files never rely on these: they name what
their builds need themselves.

On macOS and Windows there is nothing to do. On a Linux without apt, it
prints the commands, for that system's own packages.
"""

import os
import platform
import shutil
import subprocess
import sys

# Each package, with the commands it brings.
PACKAGES = {
    "bc": "bc",
    "bind9-dnsutils": "nslookup",
    "binutils": "strings",
    "bsdextrautils": "col, column, hexdump, look",
    "bzip2": "bzip2, bunzip2, bzcat",
    "cpio": "cpio",
    "curl": "curl",
    "dc": "dc",
    "ed": "ed",
    "file": "file",
    "iputils-ping": "ping",
    "less": "less",
    "lsof": "lsof",
    "ncal": "cal",
    "net-tools": "netstat",
    "patch": "patch",
    "plocate": "locate",
    "psmisc": "killall",
    "sharutils": "uuencode, uudecode",
    "uuid-runtime": "uuidgen",
    "xxd": "xxd",
}


def installed(package):
    """Whether a package is installed."""
    status = subprocess.run(["dpkg-query", "-W", "-f=${Status}", package], check=False, capture_output=True,
                            text=True)
    return status.returncode == 0 and status.stdout.endswith("ok installed")


def main():
    if platform.system() != "Linux":
        print(f"Nothing to do on {platform.system()}: niubash and BusyBox, or the system itself, bring these.")
        return 0
    if not shutil.which("apt-get") or not shutil.which("dpkg-query"):
        print("This Linux has no apt. Install its own packages for these commands:")
        for commands in PACKAGES.values():
            print(f"  {commands}")
        return 1
    missing = [package for package in PACKAGES if not installed(package)]
    if not missing:
        print(f"All {len(PACKAGES)} packages are installed.")
        return 0
    sudo = [] if os.geteuid() == 0 else ["sudo"]
    env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
    for command in (["apt-get", "update"], ["apt-get", "install", "-y", "--no-install-recommends", *missing]):
        print(f"$ {' '.join(sudo + command)}", flush=True)
        if subprocess.run(sudo + command, check=False, env=env).returncode != 0:
            sys.exit(f"{command[0]} failed; see its output above.")
    still = [package for package in missing if not installed(package)]
    if still:
        sys.exit(f"apt did not install {', '.join(still)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
