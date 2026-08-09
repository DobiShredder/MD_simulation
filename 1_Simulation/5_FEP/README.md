# Free-energy perturbation

## 한국어

Alchemical calculation은 실제 결합·해리 경로 대신 Hamiltonian을 단계적으로
바꿉니다. 인접한 lambda state가 비슷한 configuration을 sampling해야 state
사이의 free-energy 차이를 계산할 수 있습니다.

| Tutorial | 계산 | System |
| --- | --- | --- |
| [5.1 RBFE](5.1_RBFE/) | 두 ligand의 상대 결합 자유에너지 | T4 lysozyme L99A, benzene → toluene |
| [5.2 ABFE](5.2_ABFE/) | 한 ligand의 표준 결합 자유에너지 | Trypsin–benzamidine, PDB 3PTB |

두 예제 모두 AMBER TI를 사용합니다. `anal.py`는 lambda별 평균 derivative를
적분해 Gibbs free energy를 계산합니다. Window당 2 ns는 실행 가능한 tutorial
기본값이며 수렴된 연구 결과를 보장하지 않습니다.

## English

Alchemical calculations connect Hamiltonian end states instead of sampling a
physical binding or unbinding path. Neighboring lambda states must sample
overlapping configurations for reliable free-energy estimates.

The RBFE example transforms benzene into toluene in T4 lysozyme L99A. The ABFE
example applies a restrained double-decoupling cycle to benzamidine bound to
trypsin. Both use AMBER TI and two nanoseconds of production per window as a
tutorial-scale default.
