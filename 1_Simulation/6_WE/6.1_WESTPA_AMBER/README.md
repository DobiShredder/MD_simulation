# Weighted Ensemble with WESTPA and AMBER / WESTPA–AMBER WE

Reference syntax: Amber 2026 and WESTPA 2.

## 한국어

### 설정

WESTPA가 walker weight와 split/merge resampling을 관리하고 AMBER가 각
segment를 전파합니다. Progress coordinate는 Na⁺–Cl⁻ distance(Å)입니다.
Implicit solvent에서 8 Å ion pair 접근을 sampling합니다.

### 실행

필수 프로그램은 tleap, sander 또는 pmemd, cpptraj, WESTPA 2와 NumPy입니다.

~~~bash
cd 1_Simulation/6_WE/6.1_WESTPA_AMBER
AMBER_ENGINE=sander ./prepare.sh
./init.sh
./run.sh
~~~

`prepare.sh`는 minimization 뒤 고정 seed로 초기 velocity를 만듭니다. 각
segment는 `irest=1`, `ntx=5`로 parent velocity를 이어받고 `WEST_RAND32`에서
Langevin seed를 만듭니다. `west.cfg`의 기본값은 bin당 walker 4개, 1 ps
segment와 20 iterations입니다.

`west.h5`의 total weight, 실패 segment와 progress-coordinate 범위를
확인합니다. WE kinetics analysis는 아직 포함하지 않았습니다. 이 설정은
workflow test용이며 ion-association rate 계산용이 아닙니다.

## English

### Method and run

WESTPA owns walker weights and split/merge resampling; AMBER propagates each
segment. The one-dimensional progress coordinate is the Na⁺–Cl⁻ distance in Å.
Run prepare.sh, init.sh, and run.sh as shown above. The initial velocity seed is
fixed, while every continuation segment inherits parent velocities with
irest=1/ntx=5 and obtains an independent Langevin seed from WEST_RAND32.

The four walkers per bin, 1 ps segments, and 20 iterations are workflow-test
settings only. Check segment failures, total probability in west.h5, and the
sampled coordinate range. Production rate estimates require a validated model,
independent runs, much longer sampling, and uncertainty analysis.
