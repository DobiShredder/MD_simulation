# Conversion and sampling / 변환 및 frame sampling

## 한국어

한 개 이상의 trajectory를 연결하고 선택한 frame을 NetCDF와 DCD로 변환합니다.
첫 선택 frame은 PDB로 추출하며 원본 trajectory와 frame 번호의 mapping도
기록합니다.

```bash
TOPOLOGY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/system.parm7
TRAJECTORY=../../../1_Simulation/1_MD/1.1_Soluble_Protein/work/production.nc

START_FRAME=1 STOP_FRAME=last STRIDE=5 \
    ./run.sh "$TOPOLOGY" "$TRAJECTORY"
python3 anal.py
```

`run.sh`는 cpptraj 변환 뒤 `frame_map.py`를 호출합니다. 주요 output은
`sampled.nc`, `sampled.dcd`, `first_frame.pdb`와 `frame_map.tsv`입니다.
`anal.py`는 output frame과 각 source trajectory의 원본 frame 관계를 표시합니다.

여러 trajectory를 command 뒤에 순서대로 추가하면 cpptraj이 같은 topology로
연결합니다. `START_FRAME`, `STOP_FRAME`과 `STRIDE`는 각 `trajin`에 적용됩니다.
DCD는 program마다 unit-cell metadata 처리 방식이 다를 수 있으므로 후속 도구가
NetCDF를 지원하면 `sampled.nc`를 우선 사용합니다.

## English

One or more trajectories are concatenated and sampled into NetCDF and DCD.
The first selected frame is also written as PDB. `run.sh` calls `frame_map.py`
to create `frame_map.tsv`, and `anal.py` displays the source-to-output frame
mapping. Frame limits and stride apply to each input trajectory. Prefer the
NetCDF output when downstream handling of DCD unit-cell metadata is uncertain.
