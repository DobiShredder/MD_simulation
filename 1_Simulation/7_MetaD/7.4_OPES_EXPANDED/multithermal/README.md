# Multithermal OPES Expanded / 다중온도 OPES Expanded

## 한국어

`opes/plumed.dat`은 AMBER ENERGY와 radius of gyration을 출력하고 300–500 K
multithermal ECV를 bias합니다. `ATOMS=1-100`은 example selection입니다.
`ENERGY` action과 atom selection은 실행할 system에 맞게 수정합니다.

~~~bash
cd 1_Simulation/7_MetaD/7.4_OPES_EXPANDED/multithermal
# wat.parm7/wat.rst7 및 OPES-enabled PLUMED–AMBER 준비
bash run.sh
~~~

Output은 `DELTAFS`/`opes.log`, `COLVAR_MULTI_T`와 trajectory입니다. Restart에는
`DELTAFS` 또는 `STATE_RFILE`과 AMBER restart를 함께 사용합니다. Analysis에서는
temperature별 energy overlap, round trip과 effective sample size를 봅니다.

## English

The PLUMED input biases an ECV_MULTITHERMAL target from 300 to 500 K and prints
AMBER energy, radius of gyration, and bias. Check the ENERGY interface,
`ATOMS=1-100`, and physical validity of the model over the full temperature range.

Provide AMBER inputs and an OPES-enabled PLUMED build, shorten the run, and
execute `run.sh`. Preserve `DELTAFS` or `STATE_RFILE` together with the AMBER
restart. Check temperature-space round trips, reweighted overlap, effective sample
size, and observable convergence.
