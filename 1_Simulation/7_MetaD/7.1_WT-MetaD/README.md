# Well-Tempered Metadynamics

![WT-MetaD에서 감소하는 Gaussian hill height / Decreasing Gaussian hill height in WT-MetaD](../../../assets/simulation/well_tempered_hills.svg)

*Bias가 쌓일수록 새로 추가되는 hill의 height가 감소합니다. / Newly deposited hills become smaller as the bias accumulates.*


## 한국어

Alanine dipeptide의 φ와 ψ torsion에 well-tempered MetaD bias를 적용합니다.
방문한 위치에 Gaussian을 쌓되, bias가 누적될수록 높이를 낮춰 일반 MetaD보다
완만하게 free-energy surface를 채웁니다.

### 실행

```bash
cd 1_Simulation/7_MetaD/7.1_WT-MetaD
./build.sh structure/alanine-dipeptide.pdb
./run.sh --dry-run
./run.sh
python3 anal.py
```

`WORK_DIR`, `AMBER_ENGINE`, `AMBER_OPTIONS`, `PLUMED`, `TLEAP`과
`RANDOM_SEED`로 실행 환경을 바꿀 수 있습니다. `RANDOM_SEED`는 positive
integer이며 segment마다 서로 다른 seed가 생성됩니다.

### Script 역할

| File | 역할 |
|---|---|
| `build.sh` | Argument로 받은 capped alanine PDB에서 ff19SB/TIP3P solvent box와 topology를 생성합니다. |
| `check_topology.py` | build가 끝날 때 CV atom 번호와 atom 이름을 확인합니다. |
| `run.sh` | minimization, 200 ps heating, 100 ps NPT equilibration과 1 ns production을 실행합니다. |
| `anal.py` | φ/ψ 및 bias 범위를 기록하고 1 ns 누적 `HILLS`로 FES를 만듭니다. |

### 주요 option

`PACE=500`은 2 fs timestep에서 1 ps마다 Gaussian을 추가합니다. `HEIGHT=1.2`의
PLUMED 기본 energy unit은 kJ/mol이며 `SIGMA=0.2`의 단위는 radian입니다.
`BIASFACTOR=10`은 well-tempered tempering 정도를 정합니다. `GRID_MIN/MAX`는
periodic torsion의 -π–π 범위를 덮고 `CALC_RCT`가 reweighting용 offset을 계산합니다.

첫 segment는 새 `HILLS`를 만듭니다. 다음 segment는 이전 누적 `HILLS`를 복사하고
PLUMED의 `RESTART`를 사용합니다. `md.rst7`, trajectory, log, `COLVAR`와
`HILLS` 중 일부만 있으면 해당 segment에서 중단합니다. `HILLS`는 bias를
복원하는 기록이며 `COLVAR`를 대신하지 않습니다.

1 ns는 workflow 학습용 길이입니다. φ/ψ 공간의 수렴이나 정량 free energy를
입증하지 않습니다. Keyword는 PLUMED 2.10
[`METAD`](https://www.plumed.org/doc-v2.10/user-doc/html/_m_e_t_a_d.html)를
기준으로 작성했습니다.

PLUMED가 없는 분석 환경에서는 `python3 anal.py --skip-fes`로 diagnostic TSV만
생성할 수 있습니다. FES 비교는 sampling 진행 상황을 보는 용도이며 수렴 판정은
별도의 반복 계산과 오차 분석이 필요합니다.

## English

This example biases the φ and ψ torsions of alanine dipeptide with
well-tempered metadynamics. `PACE=500` deposits a Gaussian every 1 ps,
`HEIGHT=1.2` is in kJ/mol, `SIGMA=0.2` is in radians, and `BIASFACTOR=10`
controls tempering. The -π to π grid supports `CALC_RCT`.

`build.sh structure/alanine-dipeptide.pdb` creates and validates the
ff19SB/TIP3P system from the supplied PDB. `run.sh` performs
minimization, 200 ps heating, 100 ps NPT equilibration, and one 1 ns production
segment. A continuation copies the cumulative `HILLS` file and enables
PLUMED `RESTART`. `anal.py` reports sampled torsion and bias ranges. The 1 ns
run demonstrates the workflow and is not evidence of converged free energies.
