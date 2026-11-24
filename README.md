<!-- Copyright © 2026 Ömer Göktaş. All Rights Reserved. -->

# mise-config

Ömer's global mise setup: the developer tools and tasks that mise loads in every folder of a developer machine.

- `mise.toml`: the tools, such as git, gh, fnox, the formatters and the linters, and the tasks, such as `gh`, `git`, `remote:linux`, `sound` and `translate`. It holds no secret: a task that needs one runs its program through `fnox exec --only <NAME>`, or, as `translate` does, asks fnox for it in its own env when it runs, and the file's `[env]` points fnox at the `fnox` folder.
- `fnox/config.toml`: fnox's global file, the tasks' secrets encrypted with age. The age keys that open them lie beside it in `fnox/keys/`, which `.gitignore` leaves out.
- `mise.lock` and `locks/`: the exact download of every tool for macOS, Linux and Windows on AMD64 and ARM64.
- `tasks/`: the `basics` task, which installs on Debian and Ubuntu the basic commands every machine shares.

## A New Machine

1. Install mise, on Windows with the one PowerShell command of the Yastik project's `USERTASKS.md`, which also puts mise's shims folder, `%USERPROFILE%\.local\share\mise\bin`, first on the user's `Path`; then make the shell load it with `mise activate`. Set `MISE_DATA_DIR` to `~/.local/share/mise` and `MISE_CACHE_DIR` to `~/.cache/mise` before mise first runs, as that file's commands do on every system, so mise keeps the same folders everywhere; no mise file can set them.
2. Copy the whole `~/.config/mise` folder from another machine of yours, or clone this repository there, which is public.
3. Copy the `~/.config/mise/fnox/keys` folder from another machine of yours, if step 2 cloned the repository: the age keys, `age-pc.txt`, which opens the secrets and which `mise.toml`'s `FNOX_AGE_KEY_FILE` names, and `age-ci.txt`, CI's. No repository holds the keys; without them, the tasks that need a secret, such as `git` and `gh`, do not run.
4. Run `mise install` in the home folder.

## Keeping It Up to Date

A change to the setup, such as a new tool or a new lock from `mise lock --global`, changes the files here; a secret stored with `fnox set --global <NAME> --provider age` changes `fnox/config.toml`. Commit and push it from this folder, and pull it on every other machine:

```bash
cd ~/.config/mise && mise run git add -A && mise run git commit -m "<what changed>" && mise run git push
cd ~/.config/mise && mise run git pull
```
