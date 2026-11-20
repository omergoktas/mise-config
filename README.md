<!-- Copyright © 2026 Ömer Göktaş. All Rights Reserved. -->

# mise-config

Ömer's global mise setup: the developer tools, tasks and encrypted secrets that mise loads in every folder of a developer machine.

- `config.toml`: the tools, such as git, gh, the formatters and the linters, and the tasks that hold a secret, such as `gh`, `git`, `remote:linux`, `sound` and `translate`. Every secret in it is encrypted with age to the key its head comment lists.
- `mise.lock` and `locks/`: the exact download of every tool for macOS, Linux and Windows on AMD64 and ARM64.
- `tasks/`: the `secret` and `secret-file` tasks, which store a secret, encrypted, in any project's mise files or in this file.

## A New Machine

1. Install mise, on Windows with the one PowerShell command of the Yastik project's `USERTASKS.md`, which also puts mise's shims folder, `%USERPROFILE%\.local\share\mise\bin`, first on the user's `Path`; then make the shell load it with `mise activate`.
2. Copy the whole `~/.config/mise` folder from another machine of yours. It holds this repository's checkout and the age keys in `secrets/`, which are never committed: `.gitignore` leaves out that folder and keeps everything else. Copying it by hand is also the only way in, since the token that logs git and gh in to this private repository is itself one of the encrypted secrets here.
3. Run `mise install` in the home folder.

## Keeping It Up to Date

A change to the setup, such as a new tool, a secret stored with `mise run secret --global` or a new lock from `mise lock --global`, changes the files here. Commit and push it from this folder, and pull it on every other machine:

```bash
cd ~/.config/mise && mise run git add -A && mise run git commit -m "<what changed>" && mise run git push
cd ~/.config/mise && mise run git pull
```
