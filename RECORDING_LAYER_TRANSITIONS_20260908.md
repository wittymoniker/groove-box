# Recording / drawing layer update — 2026-09-08

- Record Sound and Video Clip Studio both expose a Clear Recordings Table action. Clearing the table does not delete project media files or active layer tabs.
- Both systems expose Append Recording Layer and Remove Recording Layer Tab controls.
- Record Sound keeps explicit microphone/input-device selection and refresh.
- Both systems retain Bind All Layers to Selected Instrument and Bind All Layers to Carrier with Audio / Video / Both / Unbound semantics appropriate to the tab.
- Video Clip Studio drawing layers are now tabbed and appendable/removable.
- Each drawing layer has time-based Start, End, and Fade in/out values. Rendering composites all drawing layers with those time windows plus the existing graph automation (opacity/X/Y/scale/rotation).
- Recording-layer and drawing-layer state is included in project editor state; drawing images are persisted individually in the project layers directory.
- Camera recordings are not published to FFmpeg/indexing until Qt reports stopped and the container is stable/probe-readable.
- sOS staged /opt/groovebox copies match the standalone files.
- ISO packer passes `-iso-level 3` through to xorriso so a >4 GiB initramfs does not hit the ISO9660 single-extent limit.
