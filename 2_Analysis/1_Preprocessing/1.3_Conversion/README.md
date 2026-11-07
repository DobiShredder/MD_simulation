# Conversion and sampling / 변환 및 frame sampling

## 한국어

선택한 frame을 NetCDF와 DCD로 변환하고 첫 frame을 PDB로 추출합니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
```

| Output | 내용 |
| --- | --- |
| `sampled.nc` | 선택한 frame의 NetCDF trajectory(solvent 포함 전체 atom) |
| `sampled.dcd` | 같은 frame의 DCD trajectory |
| `first_frame.pdb` | 선택 범위의 첫 frame |

`run.sh`는 cpptraj log에서 처리한 frame 수를 읽어 `Frames: N`으로 출력합니다.
기본값(`start_frame=1`, `stop_frame=last`, `stride=1`)에서는 input trajectory의
frame 수와 같습니다. 세 file은 strip하지 않았으므로 `system.parm7`과 함께
사용합니다.

다른 system이나 frame 범위는 `run.sh` 상단의 `topology`, `trajectory`,
`start_frame`, `stop_frame`과 `stride`를 수정합니다.

DCD는 program마다 unit-cell metadata 처리 방식이 다를 수 있으므로 후속 도구가
NetCDF를 지원하면 `sampled.nc`를 우선 사용합니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

Selected frames are converted to NetCDF and DCD, and the first selected frame
is written as PDB.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` from this directory. The main outputs are `sampled.nc`,
`sampled.dcd`, and `first_frame.pdb`. They keep every atom, including
solvent, so use them with `system.parm7`. `run.sh` prints the number of frames
processed by cpptraj as `Frames: N`; with the defaults (`start_frame=1`,
`stop_frame=last`, `stride=1`) it equals the input frame count.

Edit `topology`, `trajectory`, `start_frame`, `stop_frame`, and `stride` at the
top of `run.sh` for another system or frame range.

Prefer NetCDF when downstream handling of DCD unit-cell metadata is uncertain.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
