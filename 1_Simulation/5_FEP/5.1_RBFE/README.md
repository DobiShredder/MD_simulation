# T4 lysozyme RBFE / T4 lysozyme RBFE

![RBFE dual topology에서 선택되는 atom / Atoms selected by the RBFE dual topology](../../../assets/simulation/rbfe_alchemical_atoms.svg)

*현재 mask는 공통 ring만이 아니라 BNZ와 MBN residue 전체를 각각 decouple하고 couple합니다. / The current masks decouple and couple the complete BNZ and MBN residues, not only the shared ring.*


## 한국어

T4 lysozyme L99A에서 benzene을 toluene으로 바꿉니다. 같은 transformation을
protein complex와 물에서 각각 계산하고 두 값의 차이로 `ΔΔG_bind`를 구합니다.
두 ligand는 중성이므로 이 예제에는 net-charge correction이 없습니다.

### Script 역할

| 파일 | 역할 | 주요 output |
| --- | --- | --- |
| `download.sh` | 4W53 PDB/mmCIF와 ligand SDF download | `structure/` |
| `prepare.py` | Protein과 bound BNZ/MBN coordinate 분리 | `protein.pdb`, `bound_*.pdb` |
| `build.sh` | GAFF2/AM1-BCC parameter와 complex 및 solvent topology 생성 | `work/build/`, `states.tsv` |
| `generate_inputs.py` | 22개 window input 생성; `build.sh`가 호출 | `work/complex/`, `work/solvent/` |
| `run.sh` | Minimization, heating, equilibration, production 실행 | Window별 restart, trajectory, log |
| `anal.py` | Cross-state energy 추출, FE-ToolKit MBAR/BAR 실행과 두 environment 조합 | `free_energy.tsv`, `overlap_matrix.tsv` |

```bash
./download.sh
python3 prepare.py structure/4W53.raw.pdb structure/protein.pdb
./build.sh structure/protein.pdb
./run.sh
python3 anal.py
```

### 주요 option

Complex와 solvent environment는 각각 lambda 0.0–1.0의 11개 window를 사용합니다.
`timask1`/`timask2`는 BNZ와 MBN end state를, `scmask1`/`scmask2`는 soft-core
대상을 지정합니다. 각 window는 200 ps heating, 100 ps NPT equilibration과
1 ns production을 실행합니다. Minimization, heating과 equilibration은
`*.out`과 `*.rst7`이 모두 있으면 건너뜁니다. 둘 중 일부만 있으면 해당 stage를
다시 실행합니다. 어느 window든 production output이 있으면 덮어쓰지 않고
계산 전에 중단합니다.

Solvent environment는 `solvatebox system TIP3PBOX 20.0`을 사용합니다. 가장 짧은
box dimension도 `cut=10 Å`의 GPU neighbor list에 필요한 공간을 갖도록 ligand와
box edge 사이에 20 Å buffer를 둡니다. Complex environment는 protein 때문에
box가 충분히 크므로 12 Å buffer를 유지합니다.

Soft-core interaction은 Amber 26의 `aces26=1` 형식을 사용합니다.
`gti_sc_cc_energy_terms='ele,vdw,ele14,vdw14'`는 soft-core와 common region
사이의 nonbonded term을 lambda에 따라 바꿉니다. 이 형식은 `pmemd.cuda`에서
실행하며 `run.sh`는 다른 engine override를 거부합니다. Minimization의
`ntmin=2`는 `ifsc=1`에서 요구되는 steepest-descent algorithm을 사용합니다.

Production의 `ifmbar=1`과 `mbar_lambda`는 각 saved configuration의 potential
energy를 11개 state에서 평가합니다. 이 계산은 현재 window의 dynamics를
바꾸지 않고 cross-state energy를 mdout에 추가합니다.

`anal.py`는 AmberTools 26의 `edgembar-amber2dats.py`로 matrix를 추출한 뒤
full matrix가 있으면 MBAR를 사용합니다. 먼 lambda state의 energy가 수치 범위를
벗어나 mdout에 `********`로 기록되면 extractor는 해당 window의 현재 state와
인접 state energy만 저장합니다. 이 경우 모든 인접 pair가 있으면 BAR로
전환하며 임의의 energy로 `********`를 대체하지 않습니다. Complex와 solvent는
각각 사용 가능한 estimator를 선택하고 `free_energy.tsv`에 이를 기록합니다.

FE-ToolKit의 automatic equilibration, correlated-sample stride와 20회
bootstrap을 사용합니다. 각 window의 `production.out`을 읽습니다. 더 긴 계산과
segment 구성은 `3_Templates/5_FEP/5.1_RBFE`에서 설정합니다. 주요 output은
다음과 같습니다.

| Output | 내용 |
| --- | --- |
| `work/free_energy.tsv` | Complex, solvent와 `ΔΔG_bind`; MBAR/BAR estimator와 uncertainty 포함 |
| `work/mbar_diagnostics.tsv` | State별 sample 수, 제거한 equilibration과 stride |
| `work/overlap_matrix.tsv` | Lambda state 사이의 overlap |
| `work/mbar/rbfe_report.html` | FE-ToolKit convergence report |

`complex_delta_g`와 `solvent_delta_g`는 같은 방향의 transformation입니다.
`relative_binding_delta_delta_g`는 complex와 solvent 계산의 차이입니다. 최종 값보다 먼저 인접
state의 overlap과 report의 equilibration warning을 확인합니다.

참고: [RCSB PDB 4W53](https://www.rcsb.org/structure/4W53)

## English

This example transforms benzene into toluene in the T4 lysozyme L99A cavity and
repeats the same transformation in water. Their difference gives the relative
binding free energy. Both ligands are neutral, so no net-charge correction is
needed.

Run `download.sh`, `prepare.py`, `build.sh`, `run.sh`, and `anal.py` in that
order. The complex and solvent environments each contain eleven lambda windows. AMBER
soft-core masks define the two ligand end states. Every window uses 200 ps of
heating, 100 ps of NPT equilibration, and one 1 ns production run.
Minimization, heating, and equilibration are skipped when both their `*.out`
and `*.rst7` files exist; incomplete pairs are rerun. Existing production output
in any window stops the workflow before it can be overwritten.

The solvent environment uses a 20 Å solute-to-box-edge buffer so its shortest
dimension is large enough for the GPU neighbor list with the 10 Å cutoff. The
protein complex retains its 12 Å buffer because that box is already larger.

The inputs use the Amber 26 `aces26=1` soft-core format and scale
`ele,vdw,ele14,vdw14` interactions between soft-core and common regions.
`run.sh` therefore requires `pmemd.cuda`. Minimization uses `ntmin=2` because
`ifsc=1` requires the steepest-descent algorithm. `ifmbar=1` evaluates every saved
configuration at all eleven lambda states without changing its propagation.

`anal.py` extracts the cross-state energy matrix and runs the AmberTools 26
FE-ToolKit. A complete matrix is analyzed with MBAR. If an energy at a distant
lambda state overflows to `********`, the extractor retains current- and
adjacent-state energies. The analysis then uses BAR when every adjacent pair is
available; it does not replace undefined energies with arbitrary values. The
complex and solvent estimators are selected independently and recorded in
`free_energy.tsv`.

The analysis writes bootstrap uncertainties, per-state sampling diagnostics,
an overlap matrix, and an HTML convergence report from each window's
`production.out`. Use `3_Templates/5_FEP/5.1_RBFE` for longer or segmented
calculations. Inspect neighboring-state overlap and equilibration warnings
before interpreting the final value.
