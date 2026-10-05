# Ratchet MD and umbrella sampling / Ratchet MD와 US

![Harmonic restraint window와 histogram overlap / Harmonic restraint windows and histogram overlap](../../assets/simulation/umbrella_overlap.svg)

*인접 window의 histogram이 겹쳐야 CV 구간 사이의 PMF를 연결할 수 있습니다. / Neighboring histograms must overlap to connect the PMF across the CV range.*



## 한국어

Chignolin terminal Cα distance를 CV로 사용합니다.

Umbrella sampling은 하나의 trajectory가 넘기 어려운 reaction-coordinate 영역을
여러 harmonic window로 나누어 sampling합니다.
Window마다 biased distribution을 얻은 뒤 overlap을 확인하고 WHAM 같은 estimator로 unbiased PMF를 복원합니다.
이 예제에서는 ratchet MD가 window 초기 구조만 공급하며 PMF에는 umbrella production만 사용합니다.

1. PLUMED `ABMD`를 이용한 ratchet MD에서 thermal fluctuation으로 end-to-end distance가 증가하는 경로를 생성합니다.
2. Ratchet MD trajectory에서 ordered seed를 추출하고, 모두 동일한 AMBER topology를 사용하는 umbrella window를 실행합니다.

Ratchet MD는 target-directed simulation이지만 constant-velocity pulling과는 다릅니다.
목표 방향의 thermal fluctuation은 허용하고 반대 방향 fluctuation은 ratchet-and-pawl bias로 억제합니다.
Conventional Steered MD는 이 튜토리얼에서는 다루지 않습니다.



### Script 흐름

| 위치 | 역할 |
| --- | --- |
| `download.sh` | 1UAO PDB/mmCIF와 checksum을 저장합니다. |
| `prepare.py` | 첫 NMR model을 선택해 Chignolin PDB를 만듭니다. |
| `prepare.sh` | Ratchet MD와 모든 window가 공유할 ff19SB/OPC topology를 만듭니다. |
| `rmd/run.sh` | ABMD pathway를 생성합니다. |
| `rmd/anal.py` | Ordered first-crossing frame을 umbrella seed로 추출합니다. |
| `us/build.sh` | Seed, 공통 topology와 restraint로 19개 window를 만듭니다. |
| `us/run.sh` | Window별 restrained simulation을 실행합니다. |

```bash
cd 1_Simulation/2_US
./download.sh
python3 prepare.py structure/1UAO.raw.pdb structure/chignolin.pdb
./prepare.sh structure/chignolin.pdb

cd rmd
./run.sh
python3 anal.py

cd ../us
./build.sh
./run.sh
```

`download.sh`는 RCSB에서 PDB와 mmCIF를 받고 checksum을 기록합니다.
`prepare.py`는 1UAO의 첫 NMR model을 선택합니다. `prepare.sh`가 만든
ff19SB/OPC `system.parm7`을 ratchet MD와 모든 umbrella
window가 공유합니다. Window별 solvation은 하지 않습니다. CV, atom index,
ABMD target, window 범위와 force constant는 chignolin용 설정입니다.

Preparation stage의 output과 restart가 모두 있으면 건너뛰고, 일부만 있으면
해당 stage를 다시 실행합니다. 기존 ratchet 또는 umbrella production output이
있으면 덮어쓰지 않고 시작 전에 중단합니다.

`tleap.in`은 20 Å OPC buffer를 추가한 뒤 atom center로 계산한 box에
0.25 Å padding을 둡니다. AmberTools 26에서 초기 density는 약
0.93 g/cm³였고, 0.8 Å 미만의 periodic overlap은 없었습니다. Padding을
제거하거나 box를 더 줄이면 반대편 water가 겹칠 수 있습니다.

- [Ratchet MD와 seed 추출](rmd/README.md)
- [Umbrella window](us/README.md)

Histogram overlap, PMF와 uncertainty는
[`2_Analysis/7_Enhanced_Sampling/`](../../2_Analysis/7_Enhanced_Sampling/README.md)에서
계산합니다.

`download.sh`는 모든 asset과 `SHA256SUMS`를 staging에서 확인한 뒤 `helpers/publish_download.py`로 게시합니다. Transfer, checksum 또는 일반 publication 실패에서는 기존 파일을 보존하며, 관련 없는 preparation 파일도 유지합니다. `structure/.download.pending`가 남으면 prepare/build와 새 download가 거부됩니다. 보존된 staging과 marker를 점검하고, marker만 삭제해 이전 파일과 새 파일을 섞어 사용하지 않습니다.

## English

The terminal Cα distance of chignolin is used as the CV. PLUMED ABMD generates
a ratchet-MD pathway, and ordered frames seed AMBER umbrella windows.

Umbrella sampling partitions a difficult reaction-coordinate range into
harmonically restrained windows. Overlapping biased distributions are later
combined to recover an unbiased PMF. Ratchet MD supplies only starting
structures here; PMF estimation uses umbrella production data.

Ratchet MD belongs broadly to target-directed or steered simulations, but it
is not constant-velocity pulling. The ratchet-and-pawl bias permits motion
toward the target and damps backward fluctuations. This repository does not
provide a separate conventional Steered-MD tutorial.

`download.sh` retrieves the PDB and mmCIF files from RCSB and records their
checksums. `prepare.py` selects the first NMR model. Run
`./prepare.sh structure/chignolin.pdb` to create
one ff19SB/OPC topology shared by ratchet MD and every
umbrella window. Seed frames are not resolvated. The CV, atom indices, target,
window range, and restraint strength are specific to chignolin.

A preparation stage is skipped when both its output and restart exist, and an
incomplete pair is rerun. Existing ratchet or umbrella production output is
detected before it can be overwritten.

The tleap build adds a 20 Å OPC buffer and defines the periodic box from
atom centers with 0.25 Å padding. With AmberTools 26 this produced an initial
density of about 0.93 g/cm³ without periodic contacts below 0.8 Å. Removing
the padding or shrinking the box further can overlap waters across opposite
box faces.

The root scripts download, prepare, and build one shared ff19SB/OPC system.
`rmd/run.sh` generates the pathway, `rmd/anal.py` extracts ordered seeds,
`us/build.sh` creates 19 windows, and `us/run.sh` propagates them.

Histogram overlap, PMF estimation, and uncertainty are handled under
`2_Analysis/7_Enhanced_Sampling/`.

## References / 참고 자료

- [PLUMED 2.10 ABMD](https://www.plumed.org/doc-v2.10/user-doc/html/_a_b_m_d.html)
- [PLUMED 2.10 DISTANCE](https://www.plumed.org/doc-v2.10/user-doc/html/_d_i_s_t_a_n_c_e.html)
- [RCSB PDB 1UAO](https://www.rcsb.org/structure/1UAO)

### 동시 실행과 input 변경

Preparation, rMD, seed analysis, window build와 window run은 상위 `work.writers/` registry를 공유합니다. 같은 window나 seed output을 쓰는 작업은 거부하고, 서로 다른 window의 run은 함께 실행할 수 있습니다.

Run은 재사용할 결과의 input을 SHA256으로 비교합니다. Topology, 최초 coordinate file, stage input, predecessor restart와 restraint가 바뀌거나 기존 결과에 identity 기록이 없으면 파일을 보존하고 거부합니다. 이 tutorial은 고정 경로를 사용하므로 변경된 계산은 새 directory에 tutorial을 복사해 시작합니다.

정상 종료, command 실패와 INT/TERM에서는 자식 process의 종료를 확인한 뒤 자기 lock만 해제합니다. SIGKILL이나 node 장애로 남은 lock은 자동 삭제하지 않습니다. Error에 표시된 lock과 `owner.json`의 host, PID, command, scope를 확인하고 scheduler와 해당 host에서 모든 writer와 자식 process가 종료됐는지 확인한 뒤 그 lock directory만 수동 제거합니다. PID가 로컬에서 보이지 않는다는 이유만으로 제거하지 않습니다. `.gate/`도 같은 확인이 필요합니다.

지원하는 `--dry-run`과 `--help`는 보호나 identity 파일을 생성하지 않습니다. 진행 중인 work를 이동하거나 identity를 수정해 재사용하지 않습니다. 보호는 로컬 filesystem과 로컬 자식 process로 검증했으며 network filesystem, remote MPI와 다른 node의 writer 종료는 미검증입니다.

### Concurrent runs and input changes

Preparation, rMD, seed analysis, window build and window runs share the parent `work.writers/` registry. Writers to the same window or seed output are rejected; independent windows may run concurrently.

Run compares inputs for result reuse with SHA256. Changed topology, initial coordinates, stage input, predecessor restart or restraint, and results without identity records, are preserved and rejected. This tutorial uses fixed paths; start changed calculations in a new tutorial copy.

Normal exit, command failure and INT/TERM release only the owned lock after child termination is verified. Locks left by SIGKILL or node failure are retained. Inspect the reported lock and its `owner.json` host, PID, command and scopes; confirm through the scheduler and owning host that all writers and children stopped before manually removing only that lock directory. A PID missing locally is not sufficient. Apply the same checks to `.gate/`.

Supported `--dry-run` and `--help` do not create writer or identity files. Do not move active work trees or edit identities to reuse results. Protection was tested on a local filesystem with local child processes; network filesystems, remote MPI and termination of writers on other nodes remain unverified.

`download.sh` validates every asset and `SHA256SUMS` in staging before publishing through `helpers/publish_download.py`. Transfer, checksum and ordinary publication failures preserve existing files, including unrelated preparation files. A retained `structure/.download.pending` blocks source readers and new downloads. Inspect the retained staging and marker; deleting only the marker can expose a mixed generation.
