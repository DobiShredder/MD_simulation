# REST3 template

## 한국어

REST2 scaling에 κ schedule을 추가합니다. 기본 schedule은 357 K까지 κ=1.0을
유지하고 450 K에서 1.020이 되도록 선형 보간합니다. 이 값은 universal default가
아니며 IDP와 force-field/water 조합별 pilot simulation에서 compactness와 exchange를
확인해야 합니다. κ 효과는 temperature predictor에 포함되지 않습니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

명시적인 κ 목록은 `[rest3_kappa]`의 `mode = "file"`과 `file`로 입력합니다.
Temperature와 κ 목록의 길이는 같아야 합니다. Runtime requirement는 REST2와
같은 patched GROMACS/PLUMED HREX build입니다. `download.sh`는 source PDB와 함께
검증된 `repex-topology-parser` 0.2.2 source를 내려받습니다.
각 replica의 preproduction은 tutorial과 같은 minimization과 NPT equilibration
순서이며 별도 heating stage는 사용하지 않습니다.

## English

REST3 adds a κ schedule to REST2 scaling. The default keeps κ at 1.0 through
357 K and linearly reaches 1.020 at 450 K. This is not a universal value; assess
compactness and exchange in a system- and force-field-specific pilot run. The
temperature predictor does not model the κ correction. File mode accepts an
explicit κ list with one value per state. Replica preproduction uses the same
minimization-to-NPT-equilibration sequence as the fixed tutorial.
