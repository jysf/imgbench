# imgbench — common commands. `just` (https://github.com/casey/just) or read
# the recipes and run the python directly. Targets Python 3.14 (stdlib-only
# core; also runs on 3.11+). Override with `just python=python3 <recipe>`.

python := "python3.14"
corpus := "corpus/images"

# List recipes
default:
    @just --list

# Report which tools + graders are installed (works with zero tools)
check:
    {{python}} -m bench check

# Run the full sweep against the corpus -> a new runs/<UTC>-<sha>/ dir
run *ARGS:
    {{python}} -m bench run --inputs {{corpus}} {{ARGS}}

# Fast/throughput run: best-of-1 + parallel encodes (size/quality gating only;
# wall-clock NOT trustworthy). Ideal for repeated CI size-regression checks.
run-fast *ARGS:
    {{python}} -m bench run --inputs {{corpus}} --fast {{ARGS}}

# Run on your LOCAL personal corpus (corpus/local, gitignored — never published)
run-local *ARGS:
    {{python}} -m bench run --inputs corpus/local {{ARGS}}

# Inspect or clear the persistent grade cache
cache *ARGS:
    {{python}} -m bench cache {{ARGS}}

# Print the encode commands without running anything
dry-run *ARGS:
    {{python}} -m bench run --inputs {{corpus}} --dry-run {{ARGS}}

# Diff two runs; exits nonzero on a size/quality regression (CI gate)
compare A B *ARGS:
    {{python}} -m bench compare {{A}} {{B}} {{ARGS}}

# Compare the two most recent runs
compare-latest:
    {{python}} -m bench compare $(ls -dt runs/*/ | sed -n 2p) runs/latest

# Verify the committed corpus sha256s match CORPUS.md
corpus-verify:
    {{python}} -m bench corpus --corpus corpus

# Capture per-tool footprint (binary size, deps, runtime)
footprint *ARGS:
    {{python}} -m bench footprint {{ARGS}}

# Run the unit + integration tests (no external tools needed)
test:
    {{python}} -m unittest discover -s tests -v

# Re-render the markdown report for an existing run dir
report RUN:
    {{python}} -c "import json,sys; from bench import report; \
        d=__import__('pathlib').Path('{{RUN}}'); \
        m=json.loads((d/'manifest.json').read_text()); \
        s=json.loads((d/'summary.json').read_text()); \
        print(report.render_markdown(s,m,run_id=d.name))"

# Build the pinned tools image and run inside it
bench-docker *ARGS:
    docker build -f tools/Dockerfile -t imgbench-tools .
    docker run --rm -v "$PWD:/work" imgbench-tools run --inputs /work/{{corpus}} --runs-root /work/runs {{ARGS}}

# Optional: render plots from a run's sweep.csv (needs requirements-optional)
plot RUN:
    {{python}} scripts/plot.py {{RUN}}
