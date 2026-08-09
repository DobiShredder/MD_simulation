# RMSD, RMSF, and Rg

## 한국어

Chignolin의 backbone RMSD, residue별 RMSF와 radius of gyration(Rg)을 한 번에
계산합니다. RMSD는 첫 frame과 average structure를 각각 reference로 사용합니다.
RMSF는 average structure에 fitting한 좌표에서 계산합니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 cpptraj의 두 `run` pass를 사용합니다. 첫 pass에서
`average.pdb`와 `rmsd_first.dat`을 만들고, 두 번째 pass에서
`rmsd_average.dat`, `rmsf_byres.dat`과 `rg.dat`을 만듭니다. `anal.py`는 세
지표를 각각 Å 단위로 표시합니다.

다른 system은 `run.sh` 상단의 두 경로를 수정합니다. RMSD와 RMSF mask는
`:1-10@CA,C,N`이고 Rg는 protein heavy atom에 질량을
적용합니다. Reference와 mask가 바뀌면 값의 의미도 바뀌므로 서로 다른 계산을
비교할 때 같은 definition을 사용합니다. 짧은 trajectory의 안정된 RMSD만으로
구조 ensemble의 수렴을 판단하지 않습니다.

## English

This example calculates backbone RMSD against the first frame and the average
structure, residue-level RMSF after fitting, and mass-weighted heavy-atom Rg.
`run.sh` reads the default Chignolin output, uses two cpptraj passes, and writes
the average structure plus four
numeric tables. `anal.py` displays all observables in Å. Keep reference and
mask definitions consistent after editing the two paths for another system.
