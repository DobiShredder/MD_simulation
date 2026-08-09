# T4 lysozyme RBFE / T4 lysozyme RBFE

## 한국어

T4 lysozyme L99A에서 benzene을 toluene으로 바꿉니다. 같은 transformation을
protein complex와 물에서 각각 계산하고 두 값의 차이로 `ΔΔG_bind`를 구합니다.
두 ligand는 중성이므로 이 예제에는 net-charge correction이 없습니다.

### Script 역할

| 파일 | 역할 | 주요 output |
| --- | --- | --- |
| `download.sh` | 4W53 PDB/mmCIF와 ligand SDF download | `structure/` |
| `prepare.py` | Protein과 bound BNZ/MBN coordinate 분리 | `protein.pdb`, `bound_*.pdb` |
| `build.sh` | GAFF2/AM1-BCC parameter와 두 leg의 topology 생성 | `work/build/`, `states.tsv` |
| `generate_inputs.py` | 22개 window input 생성; `build.sh`가 호출 | `work/legs/` |
| `run.sh` | Minimization, heating, equilibration, production 실행 | Window별 restart, trajectory, log |
| `anal.py` | `DV/DL` 적분과 leg 조합 | `window_summary.tsv`, `free_energy.tsv` |

```bash
./download.sh
python3 prepare.py structure/4W53.raw.pdb structure/protein.pdb
./build.sh structure/protein.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

### 주요 option

Complex와 solvent leg는 각각 lambda 0.0–1.0의 11개 window를 사용합니다.
`timask1`/`timask2`는 BNZ와 MBN end state를, `scmask1`/`scmask2`는 soft-core
대상을 지정합니다. 각 window는 200 ps heating, 1 ns NPT equilibration과
1 ns production segment 두 개를 실행합니다. 완성된 segment는 건너뛰며 output이
일부만 있으면 중단합니다.

Soft-core interaction은 Amber 26의 `aces26=1` 형식을 사용합니다.
`gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14'`는 soft-core와 common region
사이의 nonbonded term을 lambda에 따라 바꿉니다. 이 형식은 `pmemd.cuda`에서
실행하며 `run.sh`는 다른 engine override를 거부합니다.

`free_energy.tsv`의 `complex_delta_g`와 `solvent_delta_g`는 같은 방향의
transformation입니다. `relative_binding_delta_delta_g`는 두 leg의 차이입니다.
Lambda 간격과 sampling 길이를 바꿨다면 `window_summary.tsv`에서 derivative의
변화와 uncertainty를 먼저 확인합니다.

참고: [RCSB PDB 4W53](https://www.rcsb.org/structure/4W53)

## English

This example transforms benzene into toluene in the T4 lysozyme L99A cavity and
repeats the same transformation in water. Their difference gives the relative
binding free energy. Both ligands are neutral, so no net-charge correction is
needed.

Run `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py` in that
order. The complex and solvent legs each contain eleven lambda windows. AMBER
soft-core masks define the two ligand end states. Every window uses 200 ps of
heating, 1 ns of NPT equilibration, and two 1 ns production segments. Completed
segments resume safely; partial output stops the workflow.

The inputs use the Amber 26 `aces26=1` soft-core format and scale
`ele,vdw,ele14,vdw14` interactions between soft-core and common regions.
`run.sh` therefore requires `pmemd.cuda`.

`anal.py` integrates the AMBER `DV/DL` records and writes the two leg values and
their difference to `work/free_energy.tsv`. Inspect the per-window derivative
summary before interpreting the final value.
