<!-- Copyright © 2026 Ömer Göktaş. All Rights Reserved. -->

# mise-config

Ömer's global mise setup: the developer tools, tasks and encrypted secrets that mise loads in every folder of a developer machine.

- `config.toml`: the tools, such as git, gh, the formatters and the linters, and the tasks that hold a secret, such as `gh`, `git`, `box:linux`, `sound` and `translate`. Every secret in it is encrypted with age to the key its head comment lists.
- `mise.lock` and `locks/`: the exact download of every tool for macOS, Linux and Windows on AMD64 and ARM64.
- `tasks/`: the `secret` and `secret-file` tasks, which store a secret, encrypted, in any project's mise files or in this file.

## A New Machine

1. Install mise, and make the shell load it with `mise activate`.
2. Clone this repository as `~/.config/mise`.
3. Copy the age key, `~/.config/mise/age.txt`, from another machine of yours by hand. It is never committed: `.gitignore` keeps only the files above.
4. Run `mise install` in the home folder.
