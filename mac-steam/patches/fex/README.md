# Imported FEX patch provenance

`0006-Compile-a-guest-entry-once-when-threads-miss-together.patch` is the complete,
unmodified upstream format-patch, including its regression test:

- Author: **jgoyvaerts <1125884+jgoyvaerts@users.noreply.github.com>**.
- PR: <https://github.com/FEX-Emu/FEX/pull/6081>.
- Commit: `61663da5bc8391130e4d3fdf0797f0ff9fe44161`.
- Download: <https://github.com/FEX-Emu/FEX/commit/61663da5bc8391130e4d3fdf0797f0ff9fe44161.patch>.
- SHA-256: `6f0ad5e0408e0a193d676d4d102214403c3e72411245b870cba4e0732b17a0d5`.

Original author/date/subject, commit message and commit ID are preserved in the
patch. No backport edits were required. The PR discloses AI assistance using
Opus 5.5; importing this patch does not claim authorship of the upstream change.
The source builder includes these original patch files in its binary archive.

The source recipe applies `0002`, `0003`, `0004`, then `0006` to the pinned
`b608a47670de0ce6cca519858c2e57a2590344da` base. Patch application and repeat-build
reverse checks pass. The r2 binary contains these four patches and was built
separately from the experimental allocator cleanup. On the M3 it started native
Steam, reached AoE2's full-resolution intro in 26.5 seconds, loaded a saved
skirmish and passed F10 after Alt-Tab. The earlier unmodified upstream concurrency
regression also passed in the combined candidate (63 compilations for 63 functions
across five threads). Those results do not isolate an AoE2 speedup from PR 6081.
The installer selects r2; the older published r1 remains available for rollback.
