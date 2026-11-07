# Releasing mnemo-protocol

PyPI `mnemo-protocol` is released only from this repository. A PyPI upload
cannot be deleted, so every release passes through checks and an explicit
human approval.

## Steps

1. Merge the change to `main` by pull request with **CI gate** green.
2. In the release PR, set the version in both `pyproject.toml` and
   `mnemo_sdk/__init__.py`, and add a `## <version> (<date>)` entry to
   `CHANGELOG.md`.
3. Create a GitHub Release with tag `v<version>` on a commit that is on
   `main`. It must not be a draft or a prerelease.
4. `publish.yml` runs:
   - **release guard**: the tag, versions and changelog agree, and the commit is on `main`;
   - **CI** on the tagged commit;
   - **build**: one sdist and one wheel, `twine check --strict`;
   - **publish**: waits in the `pypi` environment for approval.
5. Review the pending deployment in the Actions run and approve it. Only then
   does the upload run, using OIDC trusted publishing with attestations.

If anything is wrong after the upload, yank the version on PyPI and release
a new patch version. A version number can never be reused.

## Repository and PyPI settings (owner, one-time)

These cannot be set from a pull request.

- **Environment `pypi`** (Settings → Environments → `pypi`):
  - Required reviewers: the owner.
  - Deployment branches and tags: *Selected branches and tags*, add the tag
    rule `v*`.
- **Branch protection for `main`** (Settings → Branches, or a ruleset):
  - Require a pull request before merging.
  - Require the status check `CI gate`.
  - Block force pushes and deletion.
- **Tag ruleset** (optional): restrict creation of `v*` tags to admins.
- **PyPI** (pypi.org → `mnemo-protocol` → Publishing): the only trusted
  publisher is owner `MnemoProtocol`, repository `mnemo-sdk`, workflow
  `publish.yml`, environment `pypi`. Remove any other publisher, including
  pending ones.
