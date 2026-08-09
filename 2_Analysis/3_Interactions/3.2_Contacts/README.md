# Contacts / 접촉 분석

## 한국어

Chignolin heavy atom 사이의 residue contact를 계산하고 contact map을
표시합니다. 첫 선택 frame에서 4.5 Å 이내인 pair를 native contact로 정의하며
sequence separation이 1 또는 2인 local pair는 제외합니다. 작고 접힌 Chignolin은
terminal 및 β-hairpin의 long-range contact를 확인하기에 알맞습니다.
아래 command는 이 directory에서 실행합니다.

```bash
./run.sh
python3 anal.py
```

`run.sh`는 cpptraj `nativecontacts`로 native/non-native atom contact와 residue
binary series를 만듭니다. `anal.py`는 같은 residue pair의 native와 non-native
series를 frame별 OR로 합쳐 0–1 contact frequency를 계산합니다. 결과는
`contact_frequency.tsv`에 기록하고 contact-count time series와 contact map을
`plt.show()`로 표시합니다.

다른 system은 `run.sh` 상단의 두 경로를 수정합니다. Cpptraj의 raw
`byresidue map`은 한 residue pair에 속한 atom-pair frequency를
더하므로 1보다 클 수 있습니다. `contact_map.dat`은 그 값을 보존하지만,
figure에는 binary `resseries present`의 평균을 사용합니다. Protein–ligand
contact로 확장할 때는
두 atom mask를 지정하고 residue 수와 plotting label을 system에 맞게 바꿉니다.

## English

Heavy-atom contacts within 4.5 Å are tracked for Chignolin, using the first
selected frame to define native contacts and excluding pairs separated by one
or two positions in sequence.
`anal.py` combines native and non-native binary residue series frame by frame,
writes a 0–1 `contact_frequency.tsv`, and displays both contact counts and a
contact map. Raw cpptraj `byresidue map` values may exceed one because they sum
atom-pair frequencies; those files are retained but are not used as the plotted
frequency matrix. Edit the two paths and contact masks for another system.
