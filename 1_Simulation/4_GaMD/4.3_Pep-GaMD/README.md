# Peptide GaMD / Pep-GaMD

Reference syntax: Amber 2026 Pep-GaMD with pmemd.cuda.

## 한국어

Pep-GaMD는 peptide와 나머지 system에 다른 boost를 적용합니다.
`timask1/scmask1=':1-10'`과 `noshakemask=':1'`은 example mask입니다. Peptide
residue와 SHAKE 제외 범위에 맞게 바꿉니다. Input filename은
`comp_wat.parm7`과 `comp_wat.rst7`입니다.

~~~bash
cd 1_Simulation/4_GaMD/4.3_Pep-GaMD
# comp_wat.parm7/comp_wat.rst7과 수정된 mask 준비
bash run.sh
~~~

`pepgamd.in`은 `irest_gamd=0`인 통계·production 결합 input이며 기본 길이는
320 ns입니다. Test에서는 production과 통계 수집 구간을 함께 줄입니다.
Output에서 boost distribution, peptide event, anharmonicity와 reweighting
범위를 확인합니다.

## English

Pep-GaMD selectively boosts peptide and environmental energy terms. The current
residue masks :1-10 and noshakemask :1 are placeholders; adapt them to the
actual peptide and topology. Provide comp_wat.parm7/comp_wat.rst7, shorten all
statistics stages consistently, then run run.sh.

The default is a 320 ns `irest_gamd=0` workflow. Check energy statistics,
boost distributions, peptide events, anharmonicity, reweighting quality, and
independent-run convergence before interpretation.
