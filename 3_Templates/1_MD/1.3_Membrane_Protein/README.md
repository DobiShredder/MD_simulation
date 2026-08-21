# Membrane-protein MD template / Membrane-protein MD template

## 한국어

이 directory만 별도로 복사해 사용할 수 있습니다. Python dependency는 복사한
directory의 `requirements.txt`를 사용해 설치합니다.

Membrane-oriented protein PDB와 사용자가 준비한 equilibrated Lipid21 bilayer
patch를 조합해 membrane system을 만듭니다. Protein orientation과 protonation은
자동으로 결정하지 않습니다. Input PDB에는 OPM membrane boundary REMARK가 있어야
하며 protein의 membrane normal은 z축이어야 합니다.

`config.toml`에서 bilayer patch 경로와 조성을 지정합니다.

```toml
bilayer_composition = "POPC=90,POPE=5,CHOL=5"
popc_bilayer_gro = "inputs/POPC.gro"
pope_bilayer_gro = "inputs/POPE.gro"
cholesterol_bilayer_gro = "inputs/CHOL15.gro"
xy_padding = 20.0
water_padding = 25.0
```

Bilayer patch는 이 repository에서 재배포하지 않습니다. 각 coordinate file의
force-field naming과 출처를 확인한 뒤 config 경로에 둡니다.

```bash
./download.sh 1K4C
# Prepare an oriented, protonated protein PDB and the three bilayer patches.
./build.sh structure/1K4C.pdb
./run.sh --dry-run
./run.sh
```

Build는 bilayer를 복제하고 protein overlap을 제거한 뒤 ff19SB/Lipid21/OPC
topology를 생성합니다. 기본 production은 anisotropic Monte Carlo pressure
coupling을 사용하며 10×10 ns segments입니다. `protein_restraint_mask`는 system의
protein와 retained pore ion/water 선택에 맞게 검토해야 합니다.
`build_membrane.py`는 `build.sh`가 자동 호출하는 bilayer 배치 helper입니다.

## English

This directory can be copied and used on its own. Install its Python
dependencies from the local `requirements.txt` after copying it.

This template combines a membrane-oriented protein PDB with user-supplied,
equilibrated Lipid21 bilayer patches. The PDB must be aligned with the membrane
normal along z and retain the OPM membrane-boundary remarks used by the builder.
The workflow does not choose orientation, protonation, pore waters, or bound
ions automatically.

Set the POPC, POPE, and cholesterol patch paths, composition, xy padding, and
water padding in `config.toml`. Bilayer coordinate patches are not redistributed
by this repository. The default run uses ff19SB/Lipid21/OPC, anisotropic Monte
Carlo pressure coupling, and ten 10 ns production segments. `build.sh` calls
`build_membrane.py` to place the bilayer and remove overlaps.
