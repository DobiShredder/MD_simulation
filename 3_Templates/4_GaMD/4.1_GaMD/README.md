# GaMD template

## 한국어

`igamd=3`으로 total potential과 dihedral energy에 dual boost를 적용합니다.
`config.toml`의 200,000-step preparation, 1,000,000-step statistics 구간을
conventional MD와 boost equilibration에 각각 사용합니다. `sigma0P`와
`sigma0D`의 기본값은 6 kcal/mol입니다.

```bash
./build.sh prepared.pdb
./run.sh --dry-run
./run.sh
```

| File | 역할 |
| --- | --- |
| `download.sh` | 선택한 source PDB 다운로드 |
| `config.toml` | build, MD 길이와 GaMD 통계 parameter |
| `build.sh` | ff19SB/OPC topology와 GaMD input 생성 |
| `run.sh` | minimization부터 segmented production까지 실행 |
| `../generate_gamd_inputs.py` | `gamd_prepare.in`과 `production.in` 생성 |

Production이 여러 segment이면 `work/001`, `work/002`, ...에 저장합니다.
완료된 segment는 marker와 output이 모두 있을 때 건너뜁니다. Partial production
또는 GaMD state는 덮어쓰지 않습니다.

## English

This template applies the `igamd=3` dual boost to total potential and dihedral
energies. Build a reviewed PDB, inspect the generated inputs and dry run, then
start the calculation. `download.sh` retrieves an unmodified source PDB,
`build.sh` creates the solvated system and inputs, and `run.sh` executes the
stages. Multi-segment production uses `work/001`, `work/002`,
and so on while preserving both MD and GaMD restart state.
