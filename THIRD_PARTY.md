# Attribution and dependencies

The original temporary-root access used [chris-ritsen/samsung-tv-root](https://github.com/chris-ritsen/samsung-tv-root), licensed under the Unlicense. The public session adapter requires a separately obtained checkout at commit `bcd6b2ce91d6b3e5bb99b7418b95c82662ac6653`. It imports that dependency at runtime; this repository does not redistribute its source, payloads, keys or releases.

The upstream archive route credits motodrizzle's earlier Samsung S90D work and the SDB entry research described by Bishop Fox. See upstream for its implementation, authors, licensing and access risks. This repository contributes the Q70D privacy selection, offline planning, narrow persistence renderer, verification and documentation; it does not claim authorship of the root technique.

Related work with different scope:

- [invaliddayta/s90c-tools](https://github.com/invaliddayta/s90c-tools): Samsung S90C/Tizen 7 access and app-cleanup tooling (MIT).
- [ardazeytin/samsung-tizen-tv-debloat](https://github.com/ardazeytin/samsung-tizen-tv-debloat): a general storage/preinstalled-app removal guide (MIT).

No code from those two projects is included. Their compatibility and removal lists do not establish compatibility with this Q70D registry-disable workflow.

Samsung owns its firmware, system scripts and binaries. None is included. A vendor-file SHA-256 in the profile or renderer identifies tested bytes; it neither distributes those bytes nor permits substituting an unverified download for the owner's own backup.

The MIT license in this repository covers its original code, data selection and documentation only. External tools and Samsung materials retain their own terms.
