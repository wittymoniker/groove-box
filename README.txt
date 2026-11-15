MATGROOVEBOX R64 RC1 FIX8 PATCH

This is the corrected apply-ready patch for the missing overlay-sync helper
reported by the Fedora build host on 2026-11-14.

The FIX7 runner invokes:
  BUILD_ISO/sync_overlay_to_root.sh

The FIX7 apply-ready patch accidentally omitted that helper. FIX8 includes it
and installs it at the path expected by the runner. It also retains the FIX7
Secure Boot staging, import-fabric and test-policy corrections.

Apply:
  tar -xzf MATGROOVEBOX-R64-RC1-FIX8-PATCH.tar.gz
  bash MATGROOVEBOX-R64-RC1-FIX8-PATCH/APPLY_RC1_FIX8.sh \
    /home/eski/Documents/MATH_GROOVEBOX-v3

Replaced files are backed up in:
  <project>/.matgroovebox-fix8-backup/<timestamp>/

After applying, confirm:
  test -s BUILD_ISO/sync_overlay_to_root.sh
  bash -n BUILD_ISO/sync_overlay_to_root.sh BUILD_ISO/RUN_ME_v35_22.sh

Then retry the normal paired build. This patch resolves the missing-helper
exit-127 error; it does not itself certify a complete ISO, Secure Boot
signature, firmware enrollment, physical boot, or R64 feature completion.
