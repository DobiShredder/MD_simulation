# Imaging and centering / Imaging 및 centering

## 한국어

Periodic boundary condition 때문에 분리되어 보이는 molecule을 같은 primary
unit cell에 배치합니다. Chignolin residue `:1-10`을 `autoimage` anchor로
사용하며 protein center of mass와 box center의 거리를 처리 전후로 비교합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 Chignolin conventional-MD output을 직접 읽고
`inputs/cpptraj.in`을 실행합니다. 처리 전후 center를 각각
`center_raw.dat`, `center_imaged.dat`에 기록하고 `imaged.nc`를 생성합니다.
`anal.py`는 두 center-to-box distance를 Å 단위로 표시합니다.

다른 protein을 사용할 때는 `run.sh` 상단의 `topology`와 `trajectory`,
`autoimage anchor :1-10`과 두 `vector ... center` mask를 함께 바꿉니다.

## English

This example uses cpptraj `autoimage` to place molecules in a consistent
primary unit cell. Chignolin residues `:1-10` form the anchor. `run.sh` reads
the default simulation output directly and produces `imaged.nc`; `anal.py`
compares protein center-of-mass displacement from the box center. Change the
two paths, anchor, and vector masks together for another system.
