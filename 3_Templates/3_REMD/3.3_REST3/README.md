# REST3 template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

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
기본 OPC 설정에서는 `kappa_atom_names=['OW']`가 water oxygen type을 선택합니다.
`verify_rest3.py`는 O/H1/H2/EP의 type·charge·mass와 solvent interaction이
replica 사이에서 보존되는지 검사합니다. `water_model = "TIP3P"` compatibility
option도 유지합니다.
각 replica의 preproduction은 tutorial과 같은 minimization과 NPT equilibration
순서이며 별도 heating stage는 사용하지 않습니다. 첫 `grompp` 전에는 ParmEd가
출력한 긴 CMAP 실수를 GROMACS 2024.x가 읽을 수 있는 정밀도로 정규화합니다.

## English

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

REST3 adds a κ schedule to REST2 scaling. The default keeps κ at 1.0 through
357 K and linearly reaches 1.020 at 450 K. This is not a universal value; assess
compactness and exchange in a system- and force-field-specific pilot run. The
temperature predictor does not model the κ correction. File mode accepts an
explicit κ list with one value per state. Replica preproduction uses the same
minimization-to-NPT-equilibration sequence as the fixed tutorial.
With the default OPC model, `kappa_atom_names=['OW']` selects the water oxygen
type. `verify_rest3.py` checks preservation of O/H1/H2/EP atom records and
solvent interactions across replicas. The optional `water_model = "TIP3P"`
compatibility path remains available. Before the first `grompp`, the build
normalizes long ParmEd-formatted CMAP numbers to a precision accepted by
GROMACS 2024.x.
