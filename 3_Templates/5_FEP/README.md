# Free-energy templates

## 한국어

RBFE와 ABFE는 AMBER alchemical window를 생성하고 `ifmbar` energy matrix를
기록합니다. Precharged ligand MOL2와 matching frcmod를 입력으로 사용하며
charge fitting은 template가 수행하지 않습니다.

RBFE는 두 ligand mask와 atom mapping을, ABFE는 ligand mask와 여섯 restraint
anchor를 config에서 받습니다. 각 window는 20 ns production을 기본으로 합니다.
분석에는 Amber FE-ToolKit의 `edgembar-amber2dats.py`와 `edgembar`가 `PATH`에
있어야 합니다.

두 runner는 `--system complex|solvent`, 0-based inclusive
`--windows START-END`, `--preparation-only`와 `--production-only`를 지원합니다.
ABFE의 `--stage restraint|charge|vdw`는 생성된 leg만 선택합니다. 현재 RBFE
protocol은 charge와 vdW를 하나의 alchemical path에서 함께 바꾸므로 별도
`--stage`를 허용하지 않습니다.

## English

The RBFE and ABFE templates generate Amber alchemical windows and record an
`ifmbar` energy matrix. They require precharged ligand MOL2/frcmod inputs.
RBFE takes two ligand masks and an atom map; ABFE takes a ligand mask and six
explicit restraint anchors. Production defaults to 20 ns per window. Analysis
requires `edgembar-amber2dats.py` and `edgembar` from Amber FE-ToolKit on
`PATH`.

Both runners support `--system complex|solvent`, inclusive 0-based
`--windows START-END`, `--preparation-only`, and `--production-only`. ABFE
adds `--stage restraint|charge|vdw`. The current RBFE protocol couples charge
and vdW along one alchemical path and therefore rejects a separate stage.
