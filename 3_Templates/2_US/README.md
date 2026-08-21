# Umbrella sampling template

## 한국어

Reaction coordinate의 각 window를 독립적으로 sampling합니다. 사용자가 만든
target-directed trajectory에서 window center를 처음 통과하는 frame을 seed로
선택한 뒤 같은 topology와 서로 다른 harmonic restraint를 사용합니다.

`2.1_US`에서 topology build, seed/window 생성, window simulation을 순서대로
실행합니다. Reaction-coordinate atom mask와 center 목록은 system별 입력입니다.
`run.sh --window N`은 기존 1-based 단일 window interface입니다.
`--windows START-END`도 같은 1-based inclusive index를 사용합니다.
`--preparation-only`와 `--production-only`로 선택한 window의 실행 stage를
나눌 수 있습니다.

## English

Each window independently samples one region of a reaction coordinate. Seeds
are selected from the first ordered crossings of a user-provided directed
trajectory, then simulated with one shared topology and window-specific
harmonic restraints.
The existing `--window N` selector and the new inclusive
`--windows START-END` range both use 1-based indices. The selected windows can
be split into preparation and production with `--preparation-only` and
`--production-only`.
