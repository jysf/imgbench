<!-- Keep the benchmark fair and reproducible. Tick what applies. -->

## What & why

<!-- One or two sentences. -->

## Checklist

- [ ] `just test` passes (44+ tests, no external tools needed)
- [ ] Core stays **stdlib-only** (new deps behind `requirements-optional.txt`)
- [ ] If I touched an adapter: ran `just dry-run` and verified the emitted
      commands against the installed tool version
- [ ] New behavior has a test (synthetic image / fake encoder — no real tools)
- [ ] If I changed the corpus: images are redistributable, licenses + sha256
      recorded in `corpus/CORPUS.md`, and **no privacy leak** (secrets in
      screenshots, GPS in the EXIF photo)
- [ ] Equal-SSIMULACRA2 gating is preserved (no "win" at a different score)
- [ ] Docs updated if behavior/flags changed (`README.md` / `docs/`)

## Notes for reviewers

<!-- Anything fair-comparison-sensitive: timing, codec effort, metadata, threads. -->
