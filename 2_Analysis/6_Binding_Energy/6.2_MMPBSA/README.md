# MM/PBSA

## 한국어

Poisson–Boltzmann equation을 수치적으로 풀어 polar solvation energy를
계산합니다. 같은 frame에서 GB도 함께 계산해 implicit-solvent model에 따른
차이를 확인합니다.

Input trajectory, frame, topology와 decomposition 설정은
[MM/GBSA tutorial](../6.1_MMGBSA/README.md)과 같습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 running mean figure를 화면에
표시하면서 `figures/mmpbsa_running_mean.png`(150 dpi)로도 저장합니다. 저장 directory는
`output/` 밖에 둡니다. Option이 없으면 image file을 만들지 않습니다. TSV 결과는
figure 창을 열기 전에 `output/`에 기록됩니다.

`anal.py`는 GB와 PB의 energy component, ΔTOTAL running mean, block mean과
residue decomposition을 MM/GBSA와 같은 file 형식(kcal/mol)으로 기록합니다.
`model` column은 `GB`와 `PB`입니다. PB의 `term`에는 `EGB`·`ESURF` 대신 `EPB`,
`ENPOLAR`, `EDISPER`가 들어갑니다.

PB는 `istrng=0.15 M`, `indi=1.0`, `exdi=80.0`, `fillratio=4.0`, `scale=2.0`,
`inp=2`, `radiopt=0`을 사용합니다. `radiopt=0`은 topology의 mbondi2 radii를
사용한다는 뜻입니다. PB와 GB 설정과 frame 범위(`startframe`, `endframe`,
`interval`)는 이 directory의 `inputs/mmpbsa.in`에서 바꿉니다. 기본값은 MM/GBSA와
같이 모든 frame을 읽습니다.

두 model의 값이 다른 것은 solver failure가 아니며 model dependence를 보여주는
결과입니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

MM/PBSA numerically solves the Poisson–Boltzmann equation for polar solvation
and runs GB on the same frames for comparison.

The input trajectory, frames, topologies, and decomposition settings match the
[MM/GBSA tutorial](../6.1_MMGBSA/README.md). Run `./run.sh` and then
`python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the running-mean figure as
`figures/mmpbsa_running_mean.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written. TSV results are written
to `output/` before the figure window opens.

`anal.py` writes GB and PB energy components, the ΔTOTAL running mean, block
means, and residue decomposition in the same file format as MM/GBSA
(kcal/mol). The `model` column holds `GB` and `PB`; PB terms list `EPB`,
`ENPOLAR`, and `EDISPER` instead of `EGB` and `ESURF`.

PB uses 0.15 M ionic strength (`istrng`), internal/external dielectrics 1/80,
fill ratio 4, scale 2, `inp=2`, and topology mbondi2 radii (`radiopt=0`). Edit
the PB and GB settings and the frame range (`startframe`, `endframe`,
`interval`) in this directory's `inputs/mmpbsa.in`; like MM/GBSA, the default
reads all frames.

Differences between GB and PB report model dependence, not solver error.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
