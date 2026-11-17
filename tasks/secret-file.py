#!/usr/bin/env python3
#MISE description="Encrypt a key file to every key the project lists, such as `mise run secret-file ~/Downloads/developer-id.p12 signing/developer-id.p12.age`"
#MISE dir="{{cwd}}"
#MISE tools={age="1.3.2"}
#USAGE arg "<file>" help="The key file to encrypt, such as a .p12 certificate or a keystore"
#USAGE arg "<output>" help="Where the encrypted file goes, such as signing/developer-id.p12.age"
# Copyright © 2026 Ömer Göktaş. All Rights Reserved.

"""Encrypts a key file to every public age key the project's mise files list,
through the --file mode of the `secret` task's script beside this file."""

import os
import sys
from pathlib import Path

if len(sys.argv) != 3:
    sys.exit("Usage: mise run secret-file <file> <output>")
script = Path(__file__).resolve().with_name("secret.py")
os.execv(sys.executable, [sys.executable, str(script), "--file", sys.argv[1], "--output", sys.argv[2]])
