# sCodeOS distribution and self-hosting

## Replication model

sCodeOS may reproduce *its own release artifacts* from its checked-out source tree.
It does not scan for machines, copy itself to peers, auto-enroll devices, or spread across a network.

Self-hosting means:
1. source checkout;
2. test;
3. deterministic package build;
4. manifest/hash generation;
5. provenance/signature generation by CI;
6. explicit install/update by the owner.

## Distribution pathways

- GitHub source repository
- GitHub Releases: ZIP/TAR.GZ/install artifacts
- stable / beta / nightly channel JSON
- GitHub Actions build provenance
- optional Sigstore/Cosign release bundles
- offline USB/mirror distribution using the same SHA-256 + manifest verification
- later: ISO/USB installer image and package repository

## Update model

`scode_update.py` only accesses the channel URL explicitly supplied by the user.
It downloads one advertised artifact, verifies SHA-256, stages a versioned directory,
and atomically points `current` at the new release. `previous` is kept for rollback.

For production, additionally verify GitHub artifact attestations or a Sigstore bundle
before activation.

## Repository layout

- `.github/workflows/release.yml` <- copy from `distribution/github/workflows/release.yml`
- `distribution/channels/{stable,beta,nightly}.json`
- `scode_selfbuild.py`
- `scode_update.py`
- `scode_language/`
- `scode_os/`
- Master Groovebox Studio and sCode runtime

## GitHub connection note

The connected GitHub account exposed no repositories during this build, so no remote
repository was created or modified. The included bootstrap script prepares a local Git
history and prints the explicit push command instead of pushing automatically.
