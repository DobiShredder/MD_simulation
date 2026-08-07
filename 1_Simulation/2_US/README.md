# Ratchet MD and umbrella sampling / Ratchet MD와 US

## 한국어

Chignolin terminal Cα distance를 CV로 사용합니다.

1. PLUMED `ABMD`를 이용한 ratchet MD에서 thermal fluctuation으로
   end-to-end distance가 증가하는 경로를 생성합니다.
2. Ratchet MD trajectory에서 ordered seed를 추출하고, 모두 동일한 AMBER
   topology를 사용하는 umbrella window를 실행합니다.

Ratchet MD는 target-directed simulation이지만 constant-velocity pulling과는
다릅니다. 목표 방향의 thermal fluctuation은 허용하고 반대 방향 fluctuation은
ratchet-and-pawl bias로 억제합니다. Conventional Steered MD는 다루지 않습니다.

```bash
cd 1_Simulation/2_US
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./prepare.sh

cd rmd
./run.sh --dry-run
./run.sh
python3 anal.py

cd ../us
./build.sh
./run.sh --dry-run --window 1
./run.sh
```

`download.sh`는 RCSB에서 PDB와 mmCIF를 받고 checksum을 기록합니다.
`prepare.py`는 1UAO의 첫 NMR model을 선택합니다. `prepare.sh`가 만든
ff19SB/TIP3P `system.parm7`을 ratchet MD와 모든 umbrella
window가 공유합니다. Window별 solvation은 하지 않습니다. CV, atom index,
ABMD target, window 범위와 force constant는 chignolin용 설정입니다.

- [Ratchet MD와 seed 추출](rmd/README.md)
- [Umbrella window](us/README.md)

Histogram overlap, PMF와 uncertainty는
[`2_Analysis/7_Enhanced_Sampling/`](../../2_Analysis/7_Enhanced_Sampling/README.md)에서
계산합니다.

## English

The terminal Cα distance of chignolin is used as the CV. PLUMED ABMD generates
a ratchet-MD pathway, and ordered frames seed AMBER umbrella windows.

Ratchet MD belongs broadly to target-directed or steered simulations, but it
is not constant-velocity pulling. The ratchet-and-pawl bias permits motion
toward the target and damps backward fluctuations. This repository does not
provide a separate conventional Steered-MD tutorial.

`download.sh` retrieves the PDB and mmCIF files from RCSB and records their
checksums. `prepare.py` selects the first NMR model. `prepare.sh` creates
one ff19SB/TIP3P topology shared by ratchet MD and every
umbrella window. Seed frames are not resolvated. The CV, atom indices, target,
window range, and restraint strength are specific to chignolin.

Histogram overlap, PMF estimation, and uncertainty are handled under
`2_Analysis/7_Enhanced_Sampling/`.

## References / 참고 자료

- [PLUMED 2.10 ABMD](https://www.plumed.org/doc-v2.10/user-doc/html/_a_b_m_d.html)
- [PLUMED 2.10 DISTANCE](https://www.plumed.org/doc-v2.10/user-doc/html/_d_i_s_t_a_n_c_e.html)
- [RCSB PDB 1UAO](https://www.rcsb.org/structure/1UAO)
