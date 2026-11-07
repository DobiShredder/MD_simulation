# Geometry / 거리·각도·이면각

## 한국어

원자 selection으로 정의한 distance, minimum distance, angle과 backbone
dihedral을 계산합니다. Chignolin의 terminal Cα distance와 residue 1–5–10 Cα
angle은 전체 fold의 간단한 collective variable로 사용합니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/geometry.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `geometry.dat` | `Frame`, `TerminalDistance`(`:1@CA`–`:10@CA`), `MinStrandDistance`(β-strand residue 1–4와 7–10 heavy atom 사이 최소 거리), `BendAngle`(`:1@CA`–`:5@CA`–`:10@CA`) | Å, Å, degree |
| `phi_psi.dat` | `Frame`, `phi:2`, `psi:2` … `phi:9`, `psi:9` | degree(−180–180) |

`anal.py`는 distance와 angle time series 및 residue 5 Ramachandran scatter를
표시합니다. Scatter residue는 `anal.py` 상단의 `RAMACHANDRAN_RESIDUE`로 바꾸며
`multidihedral` 범위(residue 2–9) 안에서 고릅니다. Hairpin이 접혀 있는 동안
`TerminalDistance`와 `MinStrandDistance`는 작은 값에 머물고, 펴지면 함께
커집니다.

Residue 5–6은 minimum distance mask에서 뺍니다. 두 group이 붙어 있으면 공유
결합한 C(5)–N(6) 쌍이 항상 약 1.3 Å의 minimum distance가 됩니다.

다른 system은 `run.sh` 상단의 두 경로와 `inputs/cpptraj.in`의 atom mask를
수정합니다. Atom mask는 물리적으로 추적하려는 group을 반영해야 하며, residue
번호만 그대로 둔 채 다른 protein에 적용하지 않습니다.

Imaging은 계산 전에 수행하지만 원하는 molecule이 같은 image에 놓였는지도
확인합니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

The example calculates terminal Cα distance, the minimum heavy-atom distance
between the two β-strands (residues 1–4 and 7–10, `MinStrandDistance`), a
three-Cα angle, and backbone φ/ψ.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` and then `python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/geometry.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

| Output | Columns | Unit |
| --- | --- | --- |
| `geometry.dat` | `Frame`, `TerminalDistance` (`:1@CA`–`:10@CA`), `MinStrandDistance` (minimum heavy-atom distance between strands 1–4 and 7–10), `BendAngle` (`:1@CA`–`:5@CA`–`:10@CA`) | Å, Å, degree |
| `phi_psi.dat` | `Frame`, `phi:2`, `psi:2` … `phi:9`, `psi:9` | degree (−180 to 180) |

`anal.py` shows the time series and a residue-5 Ramachandran scatter; set
another residue within the `multidihedral` range (2–9) with
`RAMACHANDRAN_RESIDUE` at the top of `anal.py`. While the hairpin stays folded,
`TerminalDistance` and `MinStrandDistance` remain small; both grow when it
opens.

Residues 5–6 are excluded from the minimum-distance masks because adjacent
groups would always report the covalent C(5)–N(6) bond (about 1.3 Å).

For another system, edit the two paths in `run.sh` and redesign the atom masks
in `inputs/cpptraj.in` rather than copying the Chignolin residue numbers.
Imaging runs before the calculation, but check that the molecules of interest
share the same image.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
