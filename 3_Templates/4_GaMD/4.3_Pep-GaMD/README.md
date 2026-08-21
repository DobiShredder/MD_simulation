# Pep-GaMD template

## 한국어

`igamd=15`로 peptide potential과 나머지 system potential에 dual boost를
적용합니다. `peptide_mask`는 `config.toml`에서 지정하며 build가 실제 atom
selection을 확인합니다.

```bash
./build.sh prepared_complex.pdb
./run.sh --dry-run
./run.sh
```

Amber 26 serial `pmemd.cuda`가 필요합니다. `gamd_prepare.gamd.rst`에서 시작한
GaMD state는 각 production segment의 `production.gamd.rst`로 이어집니다.
`download.sh PDB_ID`는 source complex를 내려받고, `build.sh`는 peptide mask를
검증한 뒤 topology와 input을 생성하며, `run.sh`는 segmented GaMD를 실행합니다.

## English

This template uses `igamd=15` to boost peptide potential energy and the
remaining system potential. Set `peptide_mask` in `config.toml`; the build
verifies that it selects atoms. Amber 26 serial `pmemd.cuda` is required, and
each production segment continues both coordinate and GaMD state. `download.sh`
retrieves a source complex, `build.sh` validates the selection and writes
inputs, and `run.sh` executes the segmented workflow.
