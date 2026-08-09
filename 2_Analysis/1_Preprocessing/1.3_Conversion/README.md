# Conversion and sampling / 변환 및 frame sampling

## 한국어

선택한 frame을 NetCDF와 DCD로 변환하고 첫 frame을 PDB로 추출합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
```

주요 output은 `sampled.nc`, `sampled.dcd`와 `first_frame.pdb`입니다.
다른 system이나 frame 범위는 `run.sh` 상단의 `topology`, `trajectory`,
`start_frame`, `stop_frame`과 `stride`를 수정합니다.
DCD는 program마다 unit-cell metadata 처리 방식이 다를 수 있으므로 후속 도구가
NetCDF를 지원하면 `sampled.nc`를 우선 사용합니다.

## English

Selected frames are converted to NetCDF and DCD, and the first selected frame
is written as PDB. Edit the topology, trajectory, frame limits, and stride at
the top of `run.sh`. Prefer NetCDF when downstream handling of DCD unit-cell
metadata is uncertain.
