# OPES_METAD

## 한국어

OPES_METAD는 simulation 중에 CV distribution을 추정하고, 설정한 barrier 안에서
target distribution에 접근하도록 bias를 갱신합니다. 여기서는 alanine
dipeptide의 φ와 ψ를 bias합니다.

```bash
cd 1_Simulation/7_MetaD/7.3_OPES_METAD
./build.sh
./run.sh --dry-run
./run.sh
python3 anal.py
```

### Script 역할

| File | 역할 |
|---|---|
| `build.sh` | ff19SB/TIP3P topology를 만들고 CV atom을 확인합니다. |
| `check_topology.py` | `build.sh`가 자동 호출하며 CV atom 번호와 이름을 검사합니다. |
| `run.sh` | preparation stage와 1 ns OPES_METAD production을 실행합니다. |
| `anal.py` | φ/ψ, bias, effective sample size와 kernel 수를 segment별로 요약합니다. |

### 주요 option

`PACE=500`은 1 ps update interval입니다. `BARRIER=50` kJ/mol은 채우려는 최대
free-energy barrier를 제한하며 simulation 온도와 system에 맞춰 정해야 합니다.
`SIGMA=0.15` radian은 두 torsion의 initial kernel width입니다. `opes.rct`는
reweighting에 쓰는 offset이고 bias 자체가 아닙니다.

정확한 continuation에는 text kernel 기록만으로 충분하지 않습니다. 첫 segment가
`STATE_WFILE=opes.state`를 만들고, 이후 segment는 이전 `opes.state`를
`STATE_RFILE`로 읽습니다. 누적 `KERNELS`도 함께 이어지며 `RESTART`가 output
append 동작을 켭니다.

이 example은 adaptive state와 restart를 학습하는 용도입니다. 1 ns 결과로
정량 free energy나 수렴을 판단하지 않습니다. Keyword는 PLUMED 2.10
[`OPES_METAD`](https://www.plumed.org/doc-v2.10/user-doc/html/_o_p_e_s__m_e_t_a_d.html)를
기준으로 작성했습니다.

## English

OPES_METAD adaptively estimates the φ/ψ distribution and builds a bias bounded
by `BARRIER=50` kJ/mol. `PACE=500` updates the bias every 1 ps, and the initial
kernel widths are 0.15 rad. Exact continuation reads the binary/text OPES state
through `STATE_RFILE`; the cumulative `KERNELS` file is retained as a readable
history. `anal.py` reports CV, bias, effective-sample-size, and kernel-count
diagnostics. The 1 ns example is not a converged free-energy calculation.
