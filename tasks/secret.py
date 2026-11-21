#!/usr/bin/env python3
#MISE description="Store a secret, encrypted, in a task template of the scope's conf.d/secrets.toml, such as `mise run secret azure ATQT_AZURE_CLIENT_SECRET`"
#MISE dir="{{cwd}}"
#USAGE arg "[template]" help="The task template that holds the secret; every task that extends it gets it"
#USAGE arg "[name]" help="The variable's name"
#USAGE flag "--stdin" help="Read the value from standard input instead of asking for it"
#USAGE flag "--unredacted" help="Let the tasks' output show the value, which also lets them read standard input"
#USAGE flag "--global" help="Store it in your global mise folder's conf.d/secrets.toml, for tasks of your global mise file"
#USAGE flag "--file <file>" help="Used by secret-file: encrypt this key file instead"
#USAGE flag "--output <output>" help="Used by secret-file: where the encrypted file goes"
# Copyright © 2026 Ömer Göktaş. All Rights Reserved.

"""Stores a secret, encrypted, in a task template of a mise scope's conf.d/secrets.toml.

This file is itself the global `secret` task: mise finds every file of
~/.config/mise/tasks/ as a task in every folder, and runs it as `mise run
secret <template> <NAME>` in the folder the command starts in, which the #MISE
line above sets, since a global task would otherwise run in the home folder.

Every secret of a scope lives in one file, conf.d/secrets.toml, beside the
scope's config file: the project's in the conf.d folder of its mise folder,
such as .mise/conf.d/secrets.toml, and the user's own, with --global, in
~/.config/mise/conf.d/secrets.toml. mise loads every conf.d/*.toml file with
the config file beside it. Each secret sits in the env table of a task
template, [task_templates.<template>.env], and a task gets it by naming that
template with `extends = "<template>"`. A task extends one template, and a
template extends none, so a template holds the group of secrets that one set of
tasks needs. mise decrypts a value only while such a task runs.

The script asks mise which files it loads in the current folder (`mise config
ls --json`), and of those it takes the project's own: every file but the user's
global ones and the machine-only `*.local.toml` ones. It knows nothing else
about a project's layout, except that conf.d needs a mise folder: .mise/,
mise/ or .config/mise/.

The script asks for the value without showing it, or with --stdin reads it
from standard input, so that another program can hand it over without printing
it; a value longer than a terminal line, such as a base64 certificate, must
come through --stdin. `mise set --age-encrypt` encrypts the value, into a
scratch file, to every public age key that the comments of the scope's files
list, such as a developer's and CI's for a project, and the developer's alone
for the global scope, so a project's other keys, such as CI's, never open a
global secret. The script then writes the encrypted line into the template's
env table, in place of an earlier line of the same name, creating the table,
and the file, when there is none. It refuses a template that another file of
the scope defines. The value never reaches the screen, a log or a command line.

With --unredacted the line also says `redact = false`: mise then lets the
tasks' output show the value, and connects their standard input, which it
never does for a task whose values it redacts.

The global `secret-file` task, the file beside this one, runs it with --file
and --output instead: it encrypts a key file, such as a .p12 certificate or a
keystore, with the age command to every key the project's files list, into
the file --output names, such as signing/developer-id.p12.age in the project. A
binary file cannot be a mise value, which must be text, so key files are kept
this way.
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
TEMPLATE = re.compile(r"[A-Za-z0-9_:-]+")
# The folders of a project whose config files have a conf.d folder beside them.
MISE_FOLDERS = (".mise", "mise")

# The head of a new secrets.toml, for a project and for the global scope.
PROJECT_HEAD = """# Copyright © 2026 Ömer Göktaş. All Rights Reserved.

# The project's secrets, encrypted with age to the keys that the comments of
# its mise files list. Each group is a task template that tasks extend with
# `extends = "<template>"`, so a secret reaches only those tasks. mise loads
# this file with the project's other mise files; `mise run secret <template>
# <NAME>` writes it.
"""
GLOBAL_HEAD = """# Copyright © 2026 Ömer Göktaş. All Rights Reserved.

# The secrets of the user's own mise file, encrypted with age to the keys that
# config.toml's head comment lists. Each group is a task template that the
# tasks of config.toml extend, so a secret reaches only those tasks. mise
# loads this file with config.toml; `mise run secret --global <template>
# <NAME>` writes it.
"""


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
        if path.is_file():
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


def keys(template):
    """Returns the ways a mise file may spell the template's key, such as
    task_templates.box and task_templates."box"; a name with a colon is
    always quoted."""
    forms = [f'"{template}"']
    if re.fullmatch(r"[A-Za-z0-9_-]+", template):
        forms.insert(0, template)
    return [f"task_templates.{form}" for form in forms]


def defines(text, template):
    """Whether the mise file's text has a table of the template, its own or
    its env table."""
    headers = {line.strip() for line in text.splitlines() if line.lstrip().startswith("[")}
    return any(f"[{key}]" in headers or f"[{key}.env]" in headers for key in keys(template))


def extended(paths, template):
    """Whether a task in one of the files names the template in `extends`."""
    pattern = re.compile(rf"^\s*extends\s*=\s*[\"']{re.escape(template)}[\"']\s*$", re.MULTILINE)
    return any(path.is_file() and pattern.search(read(path)) for path in paths)


def global_folder():
    """Returns the user's global mise folder, where mise itself looks for it,
    whose conf.d folder mise loads beside its config.toml."""
    if os.environ.get("MISE_CONFIG_DIR"):
        return Path(os.environ["MISE_CONFIG_DIR"])
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "mise"


def is_global(path):
    """Whether mise loads the file as part of the user's global setup: the
    file MISE_GLOBAL_CONFIG_FILE names, or any file of the global folder."""
    named = os.environ.get("MISE_GLOBAL_CONFIG_FILE")
    if named:
        return path.resolve() == Path(named).resolve()
    return path.resolve().is_relative_to(global_folder().resolve())


def project_files():
    """Returns the mise files of the project in the current folder, as mise
    loads them: every loaded file but the global ones and the *.local.toml
    ones, which hold one machine's values and no secret."""
    result = subprocess.run([mise(), "config", "ls", "--json"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"`mise config ls` failed:\n{result.stderr.strip()}")
    files = []
    for entry in json.loads(result.stdout):
        path = Path(entry["path"])
        if path.suffix == ".toml" and ".local." not in path.name and not is_global(path):
            files.append(path)
    if not files:
        sys.exit(f"mise loads no project file in {Path.cwd()}; nothing changed.")
    return files


def project_secrets(files):
    """Returns the project's conf.d/secrets.toml: in the mise folder nearest
    the current folder, .mise/, mise/ or .config/mise/, among those whose files
    mise loads."""
    folders = []
    for path in files:
        folder = path.parent.parent if path.parent.name == "conf.d" else path.parent
        if folder.name in MISE_FOLDERS and folder not in folders:
            folders.append(folder)
    if not folders:
        sys.exit("The project keeps no mise folder, .mise/, mise/ or .config/mise/, so it has no conf.d folder for "
                 "secrets.toml; nothing changed.")
    return max(folders, key=lambda folder: len(folder.resolve().parts)) / "conf.d" / "secrets.toml"


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def store(text, template, name, line):
    """Returns secrets.toml's text with the line in the env table of the
    template, which it adds at the end when the file has none."""
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"
    headers = [i for i, l in enumerate(lines) if l.lstrip().startswith("[")]

    def table(header):
        start = next((i for i in headers if lines[i].strip() == header), None)
        if start is None:
            return None, None
        end = next((i for i in headers if i > start), len(lines))
        return start, end

    env = next((table(f"[{key}.env]") for key in keys(template) if table(f"[{key}.env]")[0] is not None), None)
    if env is None:
        owner = next(((key, *table(f"[{key}]")) for key in keys(template) if table(f"[{key}]")[0] is not None), None)
        if owner is None:
            # A new template: its own table at the end of the file.
            while lines and not lines[-1].strip():
                lines.pop()
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            lines += [newline, f"[{keys(template)[0]}.env]{newline}", line + newline]
            return "".join(lines)
        key, template_start, template_end = owner
        # Put the env table at the end of the template's own table, before the
        # blank and comment lines that open the next table.
        at = template_end
        while at > template_start + 1 and (not lines[at - 1].strip() or lines[at - 1].lstrip().startswith("#")):
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
                        help="store it in the global mise folder's conf.d/secrets.toml")
    parser.add_argument("--file", type=Path, help="encrypt this key file instead, into --output")
    parser.add_argument("--output", type=Path, help="where --file goes, encrypted")
    parser.add_argument("template", nargs="?", help="the task template that holds the secret")
    parser.add_argument("name", nargs="?", help="the variable's name")
    args = parser.parse_args()

    if args.file or args.output:
        if args.global_file:
            sys.exit("--global stores a value, not a key file.")
        if not (args.file and args.output) or args.template or args.name:
            sys.exit("--file needs --output, and no template or name.")
        recipient_keys = merged_recipients(project_files())
        if not recipient_keys:
            sys.exit("No project file lists a public age key in its comments; nothing changed.")
        encrypt_file(args.file, args.output, recipient_keys)
        print(f"Encrypted {args.file.name} to {len(recipient_keys)} key(s) as {args.output}.")
        return 0

    if not args.template or not TEMPLATE.fullmatch(args.template):
        sys.exit(f"{args.template!r} is not a template name.")
    if not args.name or not NAME.fullmatch(args.name):
        sys.exit(f"{args.name!r} is not a variable name.")

    # Find the scope's files, secrets.toml and the keys, and check them, before
    # asking for the value.
    if args.global_file:
        if os.environ.get("MISE_GLOBAL_CONFIG_FILE"):
            sys.exit("MISE_GLOBAL_CONFIG_FILE is set, and mise then loads no global conf.d folder; nothing changed.")
        folder = global_folder()
        config = folder / "config.toml"
        if not config.is_file():
            sys.exit(f"There is no global mise file at {config}; nothing changed.")
        target = folder / "conf.d" / "secrets.toml"
        files = [config, *sorted((folder / "conf.d").glob("*.toml"))]
        head = GLOBAL_HEAD
    else:
        files = project_files()
        target = project_secrets(files)
        head = PROJECT_HEAD
    files = [path for path in files if path.is_file()]
    elsewhere = [path for path in files if path.resolve() != target.resolve() and defines(read(path), args.template)]
    if elsewhere:
        sys.exit(f"{args.template} is defined in {', '.join(str(path) for path in elsewhere)}; move it into {target} "
                 "first; nothing changed.")
    recipient_keys = merged_recipients(files)
    if not recipient_keys:
        sys.exit("No file of the scope lists a public age key in its comments; nothing changed.")
    text = read(target) if target.is_file() else head
    store(text, args.template, args.name, f"{args.name} = {{}}")
    cipher = encrypt(args.name, read_value(args.name, args.stdin), recipient_keys)
    extra = ", redact = false" if args.unredacted else ""
    line = f'{args.name} = {{ age = "{cipher}"{extra} }}'
    # Write the whole new text beside the file, then put it in place in one
    # step, so a failure never leaves the file half written.
    new_text = store(text, args.template, args.name, line)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".new")
    with open(temporary, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    os.replace(temporary, target)
    print(f"Stored {args.name}, encrypted to {len(recipient_keys)} key(s), in the {args.template} template of {target}.")
    if not extended(files, args.template):
        print(f'No task extends {args.template} yet: add `extends = "{args.template}"` to each task that uses it.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
