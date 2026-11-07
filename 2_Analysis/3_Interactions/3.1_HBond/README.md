# Hydrogen bonds / 수소 결합

## 한국어

Chignolin 내부 hydrogen bond와 protein–water hydrogen bond를 분리해
계산합니다. Donor–acceptor distance는 3.0 Å 이하, donor–H–acceptor angle은
135° 이상을 사용합니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/hbond.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

`run.sh`는 `ProteinHB`와 `WaterHB` action을 실행합니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `protein_hbond_count.dat` | `Frame`, `ProteinHB[UU]`: protein 내부 hydrogen bond 수 | 개수 |
| `water_hbond_count.dat` | `Frame`, `WaterHB[UU]`, `WaterHB[UV]`(protein–water), `WaterHB[Bridge]`(bridging water 수), `WaterHB[ID]`(bridge 식별 문자열) | 개수 |
| `protein_hbond_average.dat` | `Acceptor`, `DonorH`, `Donor`, `Frames`, `Frac`(occupancy), `AvgDist`(donor–acceptor), `AvgAng` | Frac 0–1, Å, degree |
| `water_hbond_average.dat` | 같은 형식이며 `Frames` 대신 `Count`를 씁니다. | Å, degree |
| `protein_hbond_series.dat` | `Frame`, interaction별 형성 여부 | 0/1 |
| `water_hbond_series.dat` | `Frame`, solute atom별로 결합한 water 수 | 개수 |
| `water_bridge.dat` | 둘 이상의 solute residue를 연결한 water와 frame 수 | — |

`anal.py`는 count와 protein 내부 occupancy 상위 10개 항목을 표시합니다.
항목 수는 `anal.py` 상단의 `TOP_OCCUPANCY_COUNT`로 바꿉니다. Protein 내부
`Frac`은 0–1이며 1에 가까울수록 대부분의 frame에서 유지된 결합입니다. Water
쪽 `Frac`은 여러 water molecule의 결합을 합치므로 1보다 클 수 있습니다.

다른 system은 `run.sh` 상단의 두 경로와 `inputs/cpptraj.in`의 mask를
수정합니다. `solventdonor :WAT`과 `solventacceptor :WAT@O`는 AMBER의 OPC와
TIP3P가 공유하는 water naming에 맞춘 값입니다. OPC의 `EP`는 hydrogen-bond
acceptor로 선택하지 않습니다. 다른 solvent residue나 atom name을 사용하면 두
mask를 바꿉니다.

Cutoff를 바꾼 결과는 같은 hydrogen-bond definition을 사용한 결과끼리
비교합니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

The workflow separates intraprotein and protein–water hydrogen bonds using a
3.0 Å donor–acceptor distance and 135° donor–H–acceptor angle criterion.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` and then `python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/hbond.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

| Output | Columns | Unit |
| --- | --- | --- |
| `protein_hbond_count.dat` | `Frame`, `ProteinHB[UU]`: intraprotein hydrogen bonds | count |
| `water_hbond_count.dat` | `Frame`, `WaterHB[UU]`, `WaterHB[UV]` (protein–water), `WaterHB[Bridge]` (bridging waters), `WaterHB[ID]` (bridge label) | count |
| `protein_hbond_average.dat` | `Acceptor`, `DonorH`, `Donor`, `Frames`, `Frac` (occupancy), `AvgDist` (donor–acceptor), `AvgAng` | Frac 0–1, Å, degree |
| `water_hbond_average.dat` | Same layout with `Count` instead of `Frames` | Å, degree |
| `protein_hbond_series.dat` | `Frame`, presence of each interaction | 0/1 |
| `water_hbond_series.dat` | `Frame`, number of waters bonded to each solute atom | count |
| `water_bridge.dat` | Waters bridging two or more solute residues, with frame counts | — |

`anal.py` displays counts and the 10 most occupied intraprotein bonds
(`TOP_OCCUPANCY_COUNT` at the top of `anal.py`). Intraprotein `Frac` lies
between 0 and 1; values near 1 mark bonds kept in most frames. Solvent `Frac`
sums over many water molecules and can exceed 1.

For another system, edit the two paths in `run.sh` and the masks in
`inputs/cpptraj.in`. The water masks match the `WAT`/`O` names shared by AMBER
OPC and TIP3P; the OPC `EP` site is not selected as a hydrogen-bond acceptor.
Change both masks if the solvent uses different residue or atom names.

Compare results only with others that use the same hydrogen-bond definition.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
