# REST2 template

## 한국어

Water와 ion을 제외한 solute 전체를 tempered region으로 사용합니다. Temperature
predictor에는 solute atom 수와 water 0을 전달하고, 생성한 effective temperature
`T_i`에서 `lambda_pp=T_0/T_i`, `lambda_pw=sqrt(lambda_pp)`를 계산합니다.

```bash
./download.sh 1UBQ
./build.sh structure/1UBQ.pdb
replicas=$(awk 'NR > 1 {count++} END {print count + 0}' work/states.tsv)
./run.sh --cpus "$replicas" --gpus 1
```

Production에는 PLUMED 2.10이 patch된 GROMACS 2024.3/2024.6 external-MPI build와
repository tutorial에 설명한 `HREX_WORKLOAD_FIX_1` correction이 필요합니다.
`run.sh`는 시작 전에 이 marker와 `-hrex` 지원을 검사합니다. Predictor의 목표
probability는 실제 HREX acceptance를 보장하지 않으므로 짧은 pilot run에서
`Repl average probabilities`를 확인합니다.
각 replica는 tutorial과 같이 minimization 뒤 300 K velocity를 생성하는 NPT
equilibration을 실행합니다. 별도 heating stage는 두지 않습니다. Build는
scale 1 topology와 원본 topology의 single-frame potential energy 차이가
0.1 kJ/mol 이하인지도 검사합니다.

## English

The complete non-water, non-ion solute is the tempered region. The offline
predictor receives the solute atom count and zero waters, then the build derives
`lambda_pp=T_0/T_i` and `lambda_pw=sqrt(lambda_pp)` for every effective
temperature. Production requires the patched PLUMED 2.10 HREX integration and
the repository's `HREX_WORKLOAD_FIX_1` correction. Preproduction follows the
tutorial's minimization-to-NPT-equilibration sequence, and the build checks
scale-one energy identity with a 0.1 kJ/mol tolerance.
