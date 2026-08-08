# LiMaD OS 3.0 starter1-fix4 – GitHub login and remote history fix

Fix4 removes the per-run GitHub token prompt and uses GitHub CLI (`gh auth`) for persistent authentication.

For an existing repository, the starter fetches `origin/main`, writes the complete current LiMaD starter tree, and creates the new commit with the current remote main commit as its parent. This keeps the remote history and makes the normal push a fast-forward instead of requiring a force push.

Regression covered:

- no `GitHub Token (wird nicht gespeichert)` prompt
- `gh auth login --hostname github.com --git-protocol https --web` on first use
- `gh auth setup-git` for Git credentials
- existing `origin/main` becomes the parent of the new source-tree commit
- retry if the remote changes between fetch and push
- manual workflow dispatch when the exact same source tree is already online
- LiSave release manifest corrected to 1.0.0-preview3
