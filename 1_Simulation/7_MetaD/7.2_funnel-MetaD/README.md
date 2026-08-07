# Funnel Metadynamics scaffold / Funnel MetaD 초안

References: Amber 2026 and PLUMED 2.10
([FUNNEL_PS](https://www.plumed.org/doc-v2.10/user-doc/html/_f_u_n_n_e_l__p_s.html)).

## 한국어

> `metad/plumed.dat`에는 `FUNNEL_PS`/`FUNNEL` restraint가 없습니다. 현재
> 파일은 phi/psi `OPES_METAD` input이므로 Funnel-MetaD로 실행하지 않습니다.

필요한 input은 alignment reference PDB, ligand COM, funnel axis 두 점,
`ANCHOR`, funnel radius/length와 wall potential입니다. `FUNNEL_PS`의 `lp/ld`,
`WHOLEMOLECULES`와 PBC 처리를 추가하고 PLUMED funnel module을 활성화해야
합니다.

Binding free energy 계산에는 funnel-volume standard-state correction과
bound/unbound basin sampling이 추가로 필요합니다.

## English

> The current metad/plumed.dat is a phi/psi OPES_METAD example and contains no
> FUNNEL_PS or FUNNEL restraint. Do not treat this scaffold as a runnable
> Funnel-MetaD calculation.

To complete it, provide an alignment reference PDB, ligand COM, two funnel-axis
points, ANCHOR, funnel dimensions, walls, and PBC reconstruction. Connect the
FUNNEL_PS lp/ld components to the restraint and bias, enable the PLUMED funnel
module, then perform a shortened run.sh test. Binding free energies additionally
require the funnel-volume standard-state correction and converged basin sampling.
