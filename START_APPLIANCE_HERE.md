# Build / burn the Groovebox+sCode appliance

- Linux: `sudo ./appliance_tools/BUILD_AND_BURN_LINUX.sh`
- macOS: `./appliance_tools/BUILD_AND_BURN_MACOS.command`
- Windows: `./appliance_tools/BUILD_AND_BURN_WINDOWS.ps1` in PowerShell
- sCode verify: `./appliance_tools/INSTALL_WITH_SCODE.sh verify`

To burn, use the platform wrapper's explicit `--burn` / `-Burn` option. The
writer requires a whole removable disk and typed confirmation because the write
is destructive.

The appliance boots the game-ready sOS image directly into Groovebox. This build
requires its bundled sCode optimizer and refuses silent Python-only fallback.
