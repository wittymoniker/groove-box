# Groovebox R27.0.0 patch lineage and preserved invariants

Date: 2026-10-16
Version: v35.22zz-R27.0.0
Base: v35.22zz-R23r source archive, dated 2026-10-05
Release type: reconstruction increment; not the original R26 FULL3.

## Included lineage
- R23r source tree, including its inherited R23a–R23q source evolution.
- Preserved historical R23 patch artifacts copied into `PATCH_HISTORY/` for auditability. They are not blindly re-applied because R23r is already the descendant baseline.
- Existing pre-R23 preserved project documentation, test suites, cross-platform launch/build tooling, ISO build scripts, sCode assets, and app overlay sources present in the recovered source tree.
- R27.0.0 transactional export and generated-WAV installation changes, with root and ISO-overlay renderer synchronized.

## R27.0.0 changes
- Render to a suffix-preserving partial file, validate nonzero output and duration, check audio stream presence when audio inputs were supplied, then atomically replace the destination.
- Request faststart for MP4-family outputs.
- Remove stale/failed partial outputs and preserve an existing destination when rendering fails.
- Generate WAV assets into same-directory temporary files, validate before atomic publication, report asset-install errors, and process GUI events during progress updates.

## Preserved safety invariants
- Preserve the known-good v35.22zt performance/external-audio lineage and R8 installer lineage already present in source.
- Do not alter threading/Performance behavior as part of export repair.
- The known Dell ext4 `crc32c` initramfs/install failure remains an explicitly unverified/follow-up installer issue; this release does not claim to fix it.
- ISO build, VM boot, physical Dell validation, and actual WebM/MP4 playback verification have not been performed here.

## Missing history / version semantics
- R24–R26 patch payloads could not be recovered from the available Library results. No fabricated patch payloads are included.
- R27.0.0 is a new SemVer-style reconstruction increment after the recoverable R23r base, not a claim that historical R24–R26 were reconstructed exactly.
