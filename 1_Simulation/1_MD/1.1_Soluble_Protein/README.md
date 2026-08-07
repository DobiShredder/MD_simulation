# Chignolin conventional MD / Chignolin 일반 MD

## 한국어

PDB 1UAO의 첫 NMR model로 10-residue chignolin system을 만듭니다. Force
field는 ff19SB, water model은 TIP3P입니다. 계산은 minimization, 200 ps heating,
1 ns NPT equilibration과 10 ns production 순서입니다.

~~~bash
cd 1_Simulation/1_MD/1.1_Soluble_Protein
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./build.sh structure/chignolin.pdb
./run.sh --dry-run
./run.sh
~~~

`structure/SHA256SUMS`에 PDB와 mmCIF checksum이 기록됩니다. `build.sh`는
`work/system.parm7`과 `work/system.rst7`을 만듭니다. `work/leap.log`에서
unknown residue, missing atom과 net charge를 확인합니다.

Terminal state와 protonation은 build 전에 확인합니다. Heating에서 새 velocity를
만들고 이후 단계는 restart의 좌표와 velocity를 이어받습니다. 기본 engine은
`pmemd.cuda`이며 다른 실행 파일은 `AMBER_ENGINE`으로 지정합니다. 10 ns
결과는 folding equilibrium이나 수렴 판단에 사용하지 않습니다.

## English

The first NMR model of PDB 1UAO is built with ff19SB and TIP3P. The workflow runs
minimization, 200 ps heating, 1 ns NPT equilibration, and 10 ns production.

Check `structure/SHA256SUMS`, terminal states, protonation, and `work/leap.log`.
`build.sh` writes `work/system.parm7` and `work/system.rst7`. Heating creates
velocities, and later stages continue from the restart. `run.sh` uses
`pmemd.cuda`; `AMBER_ENGINE` overrides it.
The 10 ns trajectory is not a folding-equilibrium or convergence result.

## References / 참고 자료

- [RCSB PDB 1UAO](https://www.rcsb.org/structure/1UAO)
