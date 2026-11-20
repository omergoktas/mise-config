#!/usr/bin/env python3
#MISE description="Store a secret, encrypted, in the env of the mise task that uses it, such as `mise run secret ci-package ATQT_AZURE_CLIENT_SECRET`"
#MISE dir="{{cwd}}"
#USAGE arg "[task]" help="The task that uses the secret"
#USAGE arg "[name]" help="The variable's name"
#USAGE flag "--stdin" help="Read the value from standard input instead of asking for it"
#USAGE flag "--unredacted" help="Let the task's output show the value, which also lets the task read standard input"
#USAGE flag "--global" help="Store it in your global mise file, for a task defined there"
#USAGE flag "--file <file>" help="Used by secret-file: encrypt this key file instead"
#USAGE flag "--output <output>" help="Used by secret-file: where the encrypted file goes"
# Copyright © 2026 Ömer Göktaş. All Rights Reserved.

"""Stores a secret, encrypted, in the env of the mise task that uses it, in any project.

This file is itself the global `secret` task: mise finds every file of
~/.config/mise/tasks/ as a task in every folder, and runs it as `mise run
secret <task> <NAME>` in the folder the command starts in, which the #MISE
line above sets, since a global task would otherwise run in the home folder. The script asks mise which files it loads there
(`mise config ls --json`), and of those it takes the project's own: every file
but the user's global one and the machine-only `*.local.toml` ones. It knows
nothing else about a project's layout.

The script asks for the value without showing it, or with --stdin reads it
from standard input, so that another program can hand it over without printing
it; a value longer than a terminal line, such as a base64 certificate, must
come through --stdin. `mise set --age-encrypt` encrypts the value, into a
scratch file, to every public age key that the comments of the project's files
list, such as a developer's and CI's. The script then writes the encrypted line
into the one project file that defines the task, in the env table of the task
named, [tasks.<task>.env], or of the task template named,
[task_templates.<name>.env], whose value every task that extends it gets. It
replaces an earlier line of the same name, and creates the table when the task
has none. A name with a colon, such as remote:linux, is quoted in the table's
header, as TOML requires. mise decrypts the value only while such a task runs.
The value never reaches the screen, a log or a command line.

With --global the secret goes into the user's own global mise file instead,
for a task defined there, such as gh. It is encrypted to the keys that the
comments of that file list alone, so a project's other keys, such as CI's,
never open it.

With --unredacted the line also says `redact = false`: mise then lets the
task's output show the value, and connects the task's standard input, which it
never does for a task whose values it redacts.

The global `secret-file` task, the file beside this one, runs it with --file and --output instead: it encrypts a
key file, such as a .p12 certificate or a keystore, with the age command to
every key the project's files list, into the file --output names, such as
signing/developer-id.p12.age in the project. A binary file cannot be a mise
value, which must be text, so key files are kept this way.
"""

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# A public age key: "age1" and 58 letters of bech32's alphabet.
RECIPIENT = re.compile(r"\bage1[02-9ac-hj-np-z]{58}\b")
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TASK = re.compile(r"[A-Za-z0-9_:-]+")


def mise():
    path = shutil.which("mise")
    if not path:
        sys.exit("mise is not on PATH.")
    return path


def recipients(text):
    """Returns the public keys that a mise file's comment lines name."""
    found = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            found += [key for key in RECIPIENT.findall(line) if key not in found]
    return found


def merged_recipients(paths):
    found = []
    for path in paths:
        found += [key for key in recipients(read(path)) if key not in found]
    return found


def read_value(name, from_stdin):
    if from_stdin:
        value = sys.stdin.read().rstrip("\r\n")
    else:
        value = getpass.getpass(f"{name} (not shown): ")
    if not value:
        sys.exit(f"No value given for {name}; nothing changed.")
    return value


def encrypt(name, value, recipient_keys):
    """Returns the age text that `mise set` makes for the value."""
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "secret.toml"
        args = [mise(), "set", "--file", str(target), "--age-encrypt"]
        for key in recipient_keys:
            args += ["--age-recipient", key]
        args += ["--stdin", name]
        env = dict(os.environ, MISE_EXPERIMENTAL="1")
        result = subprocess.run(args, input=value, text=True, capture_output=True, env=env, check=False)
        if result.returncode != 0:
            sys.exit(f"`mise set` failed:\n{result.stderr.strip()}")
        written = target.read_text(encoding="utf-8") if target.exists() else ""
    match = re.search(rf'^{name} = \{{ age = "([A-Za-z0-9+/=]+)" \}}\s*$', written, re.MULTILINE)
    if not match:
        sys.exit(f"`mise set` wrote no encrypted line for {name}; nothing changed.")
    return match.group(1)


def keys(task):
    """Returns the ways a mise file may spell the task's or template's key,
    such as tasks.build, tasks."build" and task_templates.box; a name with a
    colon is always quoted."""
    forms = [f'"{task}"']
    if re.fullmatch(r"[A-Za-z0-9_-]+", task):
        forms.insert(0, task)
    return [f"{kind}.{form}" for kind in ("tasks", "task_templates") for form in forms]


def defines(text, task):
    """Whether the mise file's text has a table of the task or template, its
    own or its env table."""
    headers = {line.strip() for line in text.splitlines() if line.lstrip().startswith("[")}
    return any(f"[{key}]" in headers or f"[{key}.env]" in headers for key in keys(task))


def global_config():
    """Returns the user's global mise file, where mise itself looks for it."""
    if os.environ.get("MISE_GLOBAL_CONFIG_FILE"):
        return Path(os.environ["MISE_GLOBAL_CONFIG_FILE"])
    if os.environ.get("MISE_CONFIG_DIR"):
        return Path(os.environ["MISE_CONFIG_DIR"]) / "config.toml"
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "mise" / "config.toml"


def project_files():
    """Returns the mise files of the project in the current folder, as mise
    loads them: every loaded file but the global one and the *.local.toml
    ones, which hold one machine's values and no task a secret belongs to."""
    result = subprocess.run([mise(), "config", "ls", "--json"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"`mise config ls` failed:\n{result.stderr.strip()}")
    home = global_config().resolve()
    files = []
    for entry in json.loads(result.stdout):
        path = Path(entry["path"])
        if path.suffix == ".toml" and ".local." not in path.name and path.resolve() != home:
            files.append(path)
    if not files:
        sys.exit(f"mise loads no project file in {Path.cwd()}; nothing changed.")
    return files


def task_file(files, task):
    """Returns the one file that defines the task."""
    found = [path for path in files if defines(read(path), task)]
    if not found:
        sys.exit(f"No project file defines a task or task template named {task}; nothing changed.")
    if len(found) > 1:
        sys.exit(f"{task} is defined in {', '.join(str(path) for path in found)}; nothing changed.")
    return found[0]


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def store(text, task, name, line):
    """Returns the mise file's text with the line in the env table of the task
    or task template."""
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"
    headers = [i for i, l in enumerate(lines) if l.lstrip().startswith("[")]

    def table(header):
        start = next((i for i in headers if lines[i].strip() == header), None)
        if start is None:
            return None, None
        end = next((i for i in headers if i > start), len(lines))
        return start, end

    env = next((table(f"[{key}.env]") for key in keys(task) if table(f"[{key}.env]")[0] is not None), None)
    if env is None:
        owner = next(((key, *table(f"[{key}]")) for key in keys(task) if table(f"[{key}]")[0] is not None), None)
        if owner is None:
            sys.exit(f"No task or task template named {task}; nothing changed.")
        key, task_start, task_end = owner
        # Put the new table at the end of the task's own table, before the
        # blank and comment lines that open the next table.
        at = task_end
        while at > task_start + 1 and (not lines[at - 1].strip() or lines[at - 1].lstrip().startswith("#")):
            at -= 1
        if not lines[at - 1].endswith(("\n", "\r")):
            lines[at - 1] += newline
        lines[at:at] = [newline, f"[{key}.env]{newline}", line + newline]
        return "".join(lines)

    start, end = env
    for i in range(start + 1, end):
        if re.match(rf"\s*{name}\s*=", lines[i]):
            lines[i] = line + newline
            return "".join(lines)
    at = start + 1
    for i in range(start + 1, end):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("#"):
            at = i + 1
    if not lines[at - 1].endswith(("\n", "\r")):
        lines[at - 1] += newline
    lines.insert(at, line + newline)
    return "".join(lines)


def encrypt_file(source, target, recipient_keys):
    """Encrypts a key file, such as a .p12, with the age command to every
    listed key, into target, which it replaces in one step."""
    age = shutil.which("age")
    if not age:
        sys.exit("age is not on PATH; run this through `mise run secret-file`, which brings it.")
    if not source.is_file():
        sys.exit(f"{source} is not a file.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".new")
    args = [age, "--encrypt"]
    for key in recipient_keys:
        args += ["--recipient", key]
    result = subprocess.run(args + ["--output", str(temporary), str(source)],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        sys.exit(f"`age --encrypt` failed:\n{result.stderr.strip()}")
    os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stdin", action="store_true", help="read the value from standard input")
    parser.add_argument("--unredacted", action="store_true", help="add redact = false to the line")
    parser.add_argument("--global", dest="global_file", action="store_true",
                        help="store it in the user's global mise file, for a task defined there")
    parser.add_argument("--file", type=Path, help="encrypt this key file instead, into --output")
    parser.add_argument("--output", type=Path, help="where --file goes, encrypted")
    parser.add_argument("task", nargs="?", help="the task that uses the secret")
    parser.add_argument("name", nargs="?", help="the variable's name")
    args = parser.parse_args()

    if args.file or args.output:
        if args.global_file:
            sys.exit("--global stores a value, not a key file.")
        if not (args.file and args.output) or args.task or args.name:
            sys.exit("--file needs --output, and no task or name.")
        recipient_keys = merged_recipients(project_files())
        if not recipient_keys:
            sys.exit("No project file lists a public age key in its comments; nothing changed.")
        encrypt_file(args.file, args.output, recipient_keys)
        print(f"Encrypted {args.file.name} to {len(recipient_keys)} key(s) as {args.output}.")
        return 0

    if not args.task or not TASK.fullmatch(args.task):
        sys.exit(f"{args.task!r} is not a task name.")
    if not args.name or not NAME.fullmatch(args.name):
        sys.exit(f"{args.name!r} is not a variable name.")

    # Find the task's file and the keys, and check them, before asking for the
    # value.
    if args.global_file:
        config = global_config()
        if not config.is_file():
            sys.exit(f"There is no global mise file at {config}; nothing changed.")
        if not defines(read(config), args.task):
            sys.exit(f"{config} defines no task or task template named {args.task}; nothing changed.")
        recipient_keys = recipients(read(config))
    else:
        files = project_files()
        config = task_file(files, args.task)
        recipient_keys = merged_recipients(files)
    if not recipient_keys:
        sys.exit("No file lists a public age key in its comments; nothing changed.")
    text = read(config)
    store(text, args.task, args.name, f"{args.name} = {{}}")
    cipher = encrypt(args.name, read_value(args.name, args.stdin), recipient_keys)
    extra = ", redact = false" if args.unredacted else ""
    line = f'{args.name} = {{ age = "{cipher}"{extra} }}'
    # Write the whole new text beside the file, then put it in place in one
    # step, so a failure never leaves the file half written.
    new_text = store(text, args.task, args.name, line)
    temporary = config.with_name(config.name + ".new")
    with open(temporary, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    os.replace(temporary, config)
    print(f"Stored {args.name}, encrypted to {len(recipient_keys)} key(s), in the env of {args.task} in {config}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
