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
`--production-only`, `--dry-run`을 지원합니다. Preparation 또는 production에서
partial output을 발견하면 기존 파일을 보존하고 중단합니다.

빈 output도 기존 파일로 취급합니다. Completion marker와 필수 nonempty output이 모두 있어야 단계를 건너뛰며, partial output은 자동으로 덮어쓰지 않습니다.

## English

Each `windows.tsv` row gives a distance center in Å and an AMBER restraint
force constant in kcal mol⁻¹ Å⁻². `build.sh` combines each rMD seed with
the shared topology and a generated restraint. `run.sh` supports single-window,
range, preparation-only, production-only, and dry-run selection.

Empty outputs also count as existing files. A stage is skipped only when its completion marker and all required nonempty outputs exist; partial outputs are not overwritten automatically.
