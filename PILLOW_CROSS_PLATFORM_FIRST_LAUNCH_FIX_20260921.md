# v35.20b Pillow cross-platform first-launch fix

- Linux v35.20a behavior retained: run_hybrid.sh self-heals missing PIL/Pillow using the launch interpreter.
- Windows launcher now tests `import PIL` on every launch before trusting `.groovebox_provisioned_windows`.
- If PIL is missing, `install_deps_windows.ps1` runs automatically and installs Pillow with the same Python used for Groovebox.
- macOS launcher now tests `import PIL` on every launch before trusting `.groovebox_provisioned_macos`.
- If PIL is missing, `install_deps_macos.sh` runs automatically and installs Pillow with `python3`, which is also used to launch Groovebox.
- Both launchers verify `from PIL import Image` after provisioning before writing their marker.
- requirements.txt and both platform dependency installers already include Pillow.
