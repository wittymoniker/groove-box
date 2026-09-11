Groovebox GitHub release layout
===============================

The release is split into two complementary downloads:

  groovebox.zip / groovebox.tar.gz
      Main Groovebox application and cross-platform source/runtime files.
      APPLIANCE_ISO is intentionally omitted from these archives.

  BUILD_ISO.zip / BUILD_ISO.tar.gz
      The APPLIANCE_ISO builder tree only. Extract this archive into the same
      parent directory as the main release. Its paths begin with
      groovebox/APPLIANCE_ISO/, so it merges directly into the extracted
      groovebox folder.

Recommended ISO build entry point after both archives are extracted:

  cd groovebox
  sudo ./BUILD_GROOVEBOX_APPLIANCE_ISO.sh

The top-level builder restages the current Groovebox and sCode trees into the
ISO rootfs before building, so the separate BUILD_ISO package does not need to
carry a second duplicate /opt/groovebox or source/sCode copy.
