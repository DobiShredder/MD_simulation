# Protein–ligand MD template / Protein–ligand MD template

## 한국어

사용자가 준비한 complex PDB와 RESP charge가 포함된 ligand MOL2로 conventional
MD를 구성합니다. Protein은 ff19SB, ligand는 GAFF2, solvent는 OPC를 사용합니다.

`config.toml`에서 다음 경로와 chemical identity를 먼저 수정합니다.

```toml
ligand_residue_name = "LIG"
ligand_net_charge = 0
charge_method = "RESP"
ligand_mol2 = "inputs/ligand.mol2"
ligand_frcmod = "inputs/ligand.frcmod"
```

MOL2에는 RESP charge와 GAFF2 atom type이 이미 들어 있어야 합니다. 이 template는
Gaussian/ESP/RESP 계산이나 atom mapping을 자동으로 만들지 않습니다. Build는
MOL2 residue name과 net charge가 config 및 complex PDB와 일치하는지 검사합니다.

```bash
./download.sh 3HTB
# Prepare the complex PDB and place reviewed ligand parameters under inputs/.
./build.sh structure/3HTB.pdb
./run.sh --dry-run
./run.sh
```

기본값은 14 Å OPC box, 0.15 M salt, 250,000-step heating, 500,000-step
equilibration과 10×5,000,000-step production입니다. Segment가 여러 개이면
`work/001`부터 저장하며 production partial output은 자동 삭제하지 않습니다.

## English

This template builds conventional protein–ligand MD from a reviewed complex
PDB and a ligand MOL2 containing precomputed RESP charges and GAFF2 atom types.
Set the ligand residue, integer net charge, MOL2 path, and frcmod path in
`config.toml`. The build checks the MOL2 residue name and total charge against
the config and verifies that the complex PDB contains that residue.

The template does not perform quantum chemistry, RESP fitting, or atom mapping.
Its default run uses a 14 Å OPC box, approximately 0.15 M salt, 500 ps heating,
1 ns equilibration, and ten 10 ns production segments at a 2 fs timestep.
