# Native sCode bootstrap on Windows and macOS

The ordinary Groovebox launchers now install a host-native sCode stage-0 automatically.

- Windows builds `sCode/bootstrap/windows-x86_64/scode0.exe` from portable C11 source.
- macOS builds `sCode/bootstrap/macos-x86_64/scode0` or `macos-arm64/scode0` using the host architecture.
- The portable native host dispatches bootstrap compiler commands to the bundled auditable sCode compiler implementation (`scode_cli.py`). It does not copy or execute the Linux ELF on Windows/macOS.
- Windows automatically installs LLVM/clang with winget if no C compiler is available.
- macOS uses Apple clang when available and can use Homebrew LLVM.
- Repair installers remain available at `sCode/INSTALL_SCODE_WINDOWS.ps1` and `sCode/INSTALL_SCODE_MACOS.command`.
- Groovebox treats failure to build native stage-0 as a startup error rather than silently claiming native sCode is enabled.
