# Umbrella windows

## 한국어

`windows.tsv`의 각 row는 distance center(Å)와 AMBER restraint force
constant(kcal mol⁻¹ Å⁻²)를 지정합니다. `build.sh`는 rMD seed,
공통 topology와 restraint를 `work/001`, `work/002`, ...에 배치합니다.

```bash
./build.sh
./run.sh
```

`run.sh`는 `--window N`, `--windows START-END`, `--preparation-only`,
`--production-only`, `--dry-run`을 지원합니다. Incomplete preparation
stage는 다시 실행하지만 partial production은 덮어쓰지 않습니다.

## English

Each `windows.tsv` row gives a distance center in Å and an AMBER restraint
force constant in kcal mol⁻¹ Å⁻². `build.sh` combines each rMD seed with
the shared topology and a generated restraint. `run.sh` supports single-window,
range, preparation-only, production-only, and dry-run selection.
