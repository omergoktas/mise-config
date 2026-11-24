<!-- Copyright © 2026 Ömer Göktaş. All Rights Reserved. -->

# mise-config

Ömer's global mise setup: the developer tools, tasks and encrypted secrets that mise loads in every folder of a developer machine.

- `config.toml`: the tools, such as git, gh, the formatters and the linters, and the tasks, such as `gh`, `git`, `remote:linux`, `sound` and `translate`. It holds no secret; its head comment lists the age key that the secrets are encrypted to.
- `conf.d/secrets.toml`: the secrets, each encrypted with age to that key, grouped in task templates, `github`, `remote`, `sound` and `claude`, which the tasks of `config.toml` extend. mise loads it with `config.toml`.
- `mise.lock` and `locks/`: the exact download of every tool for macOS, Linux and Windows on AMD64 and ARM64.
- `tasks/`: the `secret` and `secret-file` tasks, which store a secret, encrypted, in a task template of any project's `conf.d/secrets.toml` or of this folder's, and a key file in a project's `signing` folder.

## A New Machine

1. Install mise, on Windows with the one PowerShell command of the Yastik project's `USERTASKS.md`, which also puts mise's shims folder, `%USERPROFILE%\.local\share\mise\bin`, first on the user's `Path`; then make the shell load it with `mise activate`. Set `MISE_DATA_DIR` to `~/.local/share/mise` and `MISE_CACHE_DIR` to `~/.cache/mise` before mise first runs, as that file's commands do on every system, so mise keeps the same folders everywhere; no mise file can set them.
2. Copy the whole `~/.config/mise` folder from another machine of yours. It holds this repository's checkout and the age keys in `keys/`, which are never committed: `.gitignore` leaves out that folder and keeps everything else. This repository is public, so a clone or a download of it brings everything but the keys; without them, mise cannot open the secrets, and the tasks that need one, such as `git` and `gh`, do not run.
3. Run `mise install` in the home folder.

## Keeping It Up to Date

A change to the setup, such as a new tool, a secret stored with `mise run secret --global` or a new lock from `mise lock --global`, changes the files here. Commit and push it from this folder, and pull it on every other machine:

```bash
cd ~/.config/mise && mise run git add -A && mise run git commit -m "<what changed>" && mise run git push
cd ~/.config/mise && mise run git pull
```
