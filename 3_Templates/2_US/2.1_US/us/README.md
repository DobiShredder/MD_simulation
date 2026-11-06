# Umbrella windows

## 한국어

`windows.tsv`의 각 row는 distance center(Å)와 AMBER restraint force
constant(kcal mol⁻¹ Å⁻²)를 지정합니다. 기본값 1.0은 1 Å 간격에서 300 K window 폭
약 0.55 Å로 인접 histogram이 겹치게 합니다. `build.sh`는 rMD seed,
공통 topology와 restraint를 `work/001`, `work/002`, ...에 배치합니다.
`build.sh`와 `run.sh`는 `WORK_DIR`(기본 `work`)을 같은 window root로
사용합니다. Heating input은 heavy-atom positional restraint(`ntr=1`)와 함께
AMBER manual 권장에 따라 `&ewald netfrc=0`을 씁니다.

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
force constant in kcal mol⁻¹ Å⁻². The default 1.0 gives about 0.55 Å wide 300 K
windows at 1 Å spacing, so neighboring histograms overlap. `build.sh` combines each rMD seed with
the shared topology and a generated restraint. `run.sh` supports single-window,
range, preparation-only, production-only, and dry-run selection.
Both scripts use `WORK_DIR` (default `work`) as the window root. The heating
input uses heavy-atom positional restraints (`ntr=1`) and sets
`&ewald netfrc=0`, as the AMBER manual recommends.

Empty outputs also count as existing files. A stage is skipped only when its completion marker and all required nonempty outputs exist; partial outputs are not overwritten automatically.
