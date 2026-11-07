# SASA / 용매 접근 표면적

## 한국어

LCPO algorithm으로 Chignolin 전체 solvent-accessible surface area(SASA)와 각
residue의 기여도를 계산합니다. Probe offset은 AMBER 기본값인 1.4 Å입니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/sasa.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `sasa_total.dat` | `Frame`, `Total`: protein 전체 SASA | Å² |
| `sasa_byres.dat` | `Frame`, `Res1` … `Res10`: residue별 기여 | Å² |

`anal.py`는 total time series와 residue별 평균을 표시합니다. 각 frame에서
`Res1`–`Res10`의 합은 `Total`과 같습니다. Residue 계산에는 `solutemask :1-10`을 사용하므로 각 residue가
분리된 molecule이 아니라 전체 protein에 기여하는 surface를 계산합니다.

다른 system은 `run.sh` 상단의 두 경로와 `inputs/cpptraj.in`의 SASA mask를
수정하고, residue 수에 맞춰 `anal.py` 상단의 `RESIDUE_COUNT`를 바꿉니다. 서로 다른 system이나 ligand-bound state를 비교할 때는 atom mask,
radii와 probe offset을 같게 유지합니다.

LCPO의 부분 selection 기여도는 근사식 때문에 작은 음수가 나올 수 있습니다.
이는 parser failure가 아닙니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

The LCPO algorithm calculates total Chignolin SASA and residue contributions
with the AMBER-default 1.4 Å probe offset.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` and then `python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/sasa.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

| Output | Columns | Unit |
| --- | --- | --- |
| `sasa_total.dat` | `Frame`, `Total`: total protein SASA | Å² |
| `sasa_byres.dat` | `Frame`, `Res1` … `Res10`: residue contributions | Å² |

`anal.py` displays the total time series and mean residue contributions. In
every frame, `Res1`–`Res10` sum to `Total`. `solutemask :1-10` evaluates each residue in the context
of the full protein.

For another system, edit the two paths in `run.sh`, the SASA masks in
`inputs/cpptraj.in`, and `RESIDUE_COUNT` at the top of `anal.py`. Keep atom masks, radii, and probe offset identical when
comparing systems or ligand-bound states.

Small negative contributions can occur for partial LCPO selections and are not
parser errors.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
