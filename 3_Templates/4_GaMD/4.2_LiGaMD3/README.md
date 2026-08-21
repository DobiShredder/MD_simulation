# LiGaMD3 template

## 한국어

Amber 26 `igamd=28` triple boost를 사용합니다. `ligand_mask`와
`receptor_mask`는 residue 이름으로 추정하지 않고 `config.toml`에서 받습니다.
Build 과정에서 두 mask가 atom을 선택하는지, 겹치지 않는지, receptor가
LiGaMD3의 `bgpro2atm`–`edpro2atm`에 필요한 연속 atom 범위인지 검사합니다.

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
```

Precharged RESP MOL2와 matching frcmod 경로도 config에서 지정합니다. 이
workflow는 serial `pmemd.cuda`만 지원합니다. Production segment는 MD restart와
`gamd-restart.dat`를 함께 이어받습니다.
`download.sh PDB_ID`는 source complex만 내려받으며 ligand parameter를 만들지
않습니다. `build.sh`는 topology와 GaMD input을 만들고 `run.sh`는 각 stage를
순서대로 실행합니다.

## English

This template uses the Amber 26 `igamd=28` triple boost. The ligand and receptor
masks are explicit config inputs. The build validates non-empty, non-overlapping
selections and requires the receptor to form the contiguous atom range used by
`bgpro2atm` and `edpro2atm`. Serial `pmemd.cuda` is required.
`download.sh` retrieves only a source complex; `build.sh` creates the system and
GaMD inputs, and `run.sh` propagates the stages while continuing GaMD state.
