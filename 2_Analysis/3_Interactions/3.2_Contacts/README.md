# Contacts / 접촉 분석

## 한국어

Chignolin heavy atom 사이의 residue contact를 계산하고 contact map을
표시합니다. 첫 선택 frame에서 4.5 Å 이내인 pair를 native contact로 정의하며
sequence separation이 1 또는 2인 local pair는 제외합니다. 작고 접힌 Chignolin은
terminal 및 β-hairpin의 long-range contact를 확인하기에 알맞습니다.

`run.sh`는 [Chignolin conventional MD](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md)의
`work/system.parm7`과 `work/production.nc`를 직접 읽습니다. 아래 command는 이
directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`python3 anal.py --save-figure figures`처럼 실행하면 figure를 화면에 표시하면서
`figures/contacts.png`(150 dpi)로도 저장합니다. 저장 directory는 `output/` 밖에
둡니다. Option이 없으면 image file을 만들지 않습니다.

`run.sh`는 cpptraj `nativecontacts`로 native/non-native atom contact와 residue
binary series를 만듭니다. `anal.py`는 같은 residue pair의 native와 non-native
series를 frame별 OR로 합쳐 0–1 contact frequency를 계산합니다. 결과는
`contact_frequency.tsv`에 기록하고 contact-count time series와 contact map을
`plt.show()`로 표시합니다. `contact_frequency.tsv`는 figure 창을 열기 전에
게시되므로 창을 닫거나 Ctrl-C로 중단해도 남습니다.

| Output | Column | 단위 |
| --- | --- | --- |
| `contact_count.dat` | `Frame`, `Contacts[native]`, `Contacts[nonnative]` | atom-pair 개수 |
| `contact_frequency.tsv` | `residue_1`, `residue_2`, `contact_frequency` | 0–1 |
| `contact_residue_series.dat` | `Frame`, residue pair별 contact 여부. `nn_` prefix는 non-native입니다. | 0/1 |
| `contact_pairs.dat` | Native atom contact별 `Nframes`, `Frac.`, `Avg`, `Stdev` | Frac. 0–1, distance Å |
| `contact_residue_pairs.dat` | `#Res1`, `#Res2`, `TotalFrac`(atom-pair `Frac.`의 합), `Contacts` | — |
| `native.contact_map.dat`, `nonnative.contact_map.dat` | Residue × residue raw `byresidue map` | — |
| `contact_series.dat`, `nonnative_series.dat` | Atom contact별 contact 여부 | 0/1 |

`Contacts[native]`는 첫 frame에서 전체 native contact 수이며, hairpin이 유지되는
동안 크게 줄지 않습니다.

Cpptraj의 raw `byresidue map`은 한 residue pair에 속한 atom-pair frequency를
더하므로 1보다 클 수 있습니다. `native.contact_map.dat`과
`nonnative.contact_map.dat`은 그 값을 보존하지만, figure에는 binary
`resseries present`의 평균을 사용합니다.

Native/non-native count가 모든 frame에서 0이면 `anal.py`는 0으로 채운
contact map을 만듭니다. Count가 양수이면 해당 frame의 residue series가
필요합니다.

다른 system은 `run.sh` 상단의 두 경로와 `inputs/cpptraj.in`의 mask를
수정합니다. Protein–ligand contact로 확장할 때는 두 atom mask를 지정하고
`anal.py`의 `RESIDUE_COUNT`와 plotting label을 system에 맞게 바꿉니다.

결과 게시, 실패 log(`output.failed/`), 동시 실행 보호(`writer_guard.py`)는
[GUIDE.md 부록](../../../GUIDE.md#4-부록-실행-상태와-복구)을 참고합니다.

## English

Heavy-atom contacts within 4.5 Å are tracked for Chignolin, using the first
selected frame to define native contacts and excluding pairs separated by one
or two positions in sequence.

`run.sh` reads `work/system.parm7` and `work/production.nc` from the
[Chignolin conventional-MD tutorial](../../../1_Simulation/1_MD/1.1_Soluble_Protein/README.md).
Run `./run.sh` and then `python3 anal.py` from this directory.

`python3 anal.py --save-figure figures` also saves the figure as
`figures/contacts.png` (150 dpi) while displaying it. Keep that directory outside
`output/`; without the option no image file is written.

`run.sh` runs cpptraj `nativecontacts` to write native/non-native atom contacts
and binary residue series. `anal.py` combines native and non-native residue
series frame by frame, writes a 0–1 `contact_frequency.tsv`, and displays both
contact counts and a contact map. The TSV is published before the figure
window opens, so closing the window or pressing Ctrl-C keeps it.

| Output | Columns | Unit |
| --- | --- | --- |
| `contact_count.dat` | `Frame`, `Contacts[native]`, `Contacts[nonnative]` | atom-pair count |
| `contact_frequency.tsv` | `residue_1`, `residue_2`, `contact_frequency` | 0–1 |
| `contact_residue_series.dat` | `Frame`, contact presence per residue pair; the `nn_` prefix marks non-native pairs | 0/1 |
| `contact_pairs.dat` | `Nframes`, `Frac.`, `Avg`, `Stdev` per native atom contact | Frac. 0–1, distance Å |
| `contact_residue_pairs.dat` | `#Res1`, `#Res2`, `TotalFrac` (sum of atom-pair `Frac.`), `Contacts` | — |
| `native.contact_map.dat`, `nonnative.contact_map.dat` | Raw residue × residue `byresidue map` | — |
| `contact_series.dat`, `nonnative_series.dat` | Contact presence per atom pair | 0/1 |

`Contacts[native]` equals the total native-contact count in the first frame and
stays close to it while the hairpin remains folded.

Raw cpptraj `byresidue map` values may exceed one because they sum atom-pair
frequencies; `native.contact_map.dat` and `nonnative.contact_map.dat` retain
them but are not used as the plotted frequency matrix.

If native and non-native counts are zero in every frame, `anal.py` writes a
zero contact map. Positive counts require matching residue series.

For another system, edit the two paths in `run.sh` and the masks in
`inputs/cpptraj.in`. For protein–ligand contacts, set both atom masks and adjust
`RESIDUE_COUNT` and the plot labels in `anal.py`.

Result publication, failure logs (`output.failed/`) and concurrent-run
protection (`writer_guard.py`) are described in [GUIDE.md appendix](../../../GUIDE.md#4-appendix-run-state-and-recovery).
