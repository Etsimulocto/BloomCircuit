# BloomPetz Save Format

Planned extension: `.bloompet`

A save represents one complete pet life-state and should be portable between compatible BloomPetz devices.

Required design goals:

- versioned format
- unique pet ID
- Name and Type
- one-line custom pet art
- current state and needs
- lifetime and hidden stats
- personality and habits
- milestones/history
- growth/evolution state
- integrity/checksum data
- backward-compatible migration path

The physical device keeps three active pet slots. Host storage may keep unlimited archived save files.

Exact schema is intentionally not frozen yet.
