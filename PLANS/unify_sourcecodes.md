# Unify the STM32F405 OpenGD77 source trees

## Motivation

Upstream OpenGD77 ships **one source archive per radio family**, even when the
underlying MCU and HAL are identical. This repo currently contains only the
`MDUV380_DM1701_RT3S_RT84` tree (`MDUV380_firmware/`). The MD2017/RT82 and
MD9600/RT90 firmwares are built from sibling archives that share ~90% of the
application code but live in separate zips and drift independently.

This plan describes how to fold those sibling trees into a single source tree
in this repo so that one `make build PLATFORM=<x>` produces the binary for any
supported F405-based radio.

## Source archives (as of 2026-05-31)

Discoverable at <https://opengd77.eu/>:

| Family | MCU | Latest source | URL fragment |
|---|---|---|---|
| MDUV380 / DM1701 / RT3S / RT84 | STM32F405VGT6 | 20260131 | `MDUV380_DM1701_RT3S_RT84/R20260131/sources_and_tools/` |
| MD2017 / RT82 | STM32F405VGT6 | 20260131 | `MD2017_RT82/R20260131/sources_and_tools/` |
| MD9600 / RT90 | STM32F405VGT6 | 20260131 | `MD9600_RT90/R20260131/sources_and_tools/` |
| MD380 / RT3 | STM32F405VGT6 | R20230319 (FM-only) | `MD380_RT3/R20230319_UHF_FM_ONLY/` |
| MK22 (GD77 family) | NXP MK22FN | 20240908 | `MK22/R20240908/sources_and_tools/` |

The site uses an anti-leech referer check — set `-e <listing-url>` on curl.

## Scope

**In scope:** unify MDUV380, MD2017, MD9600 into the existing
`MDUV380_firmware/` tree.

**Skip MD380:** only the 2023 FM-only fork is published; no current DMR source
is available. Unifying it produces only a stale FM-only firmware, not
something equivalent to current upstream MD380 binaries.

**Skip MK22 family** (GD77 / GD77S / RD5R / DM1801 / DM1801A): different MCU
(NXP Kinetis), different SDK (Kinetis SDK + Amazon FreeRTOS), different
startup/linker. It's a separate project. If ever vendored, keep it as a
sibling top-level dir, not merged.

## Why this is tractable

All three in-scope trees use the **same MCU** (STM32F405VGT6), the **same
linker script** (`STM32F405VGTX_FLASH.ld`), the same STM32 HAL, the same
FreeRTOS, the same USB stack, and the same directory layout (`Core/`,
`Drivers/`, `Middlewares/`, `USB_DEVICE/`, `SeggerRTT/`, `application/`,
`tools/`).

The MDUV380 source **already has the unification scaffolding in place** — its
own files contain ~191 `PLATFORM_MD2017` references, ~258 `PLATFORM_MD9600`,
~159 `PLATFORM_MD380`. The maintainer copies files between trees but doesn't
actually share them; the ifdefs are there, just unused in MDUV builds.

## What actually differs

Comparing `application/` against MDUV (167 shared files):

- **MD2017:** 97 identical, 70 differ. New files: none.
- **MD9600:** 74 identical, 86 differ. New files unique to MD9600:
  - `application/include/hardware/ST7567.h`, `ST7567_charset.h`, `ST7567_charset_JA.h`
  - `application/source/hardware/ST7567_display.c`, `ST7567_transfer.c`
  - `application/include/interfaces/remoteHead.h`
  - `application/source/interfaces/remoteHead.c`

### Real per-platform hardware differences (not drift)

- **MD2017 trackball** — head-unit navigation joystick. Touches `keyboard.c`,
  `buttons.c`, `uiLockScreen.c`, `menuGeneralOptions.c`,
  `batteryAndPowerManagement.c`, `applicationMain.c`. Implementation lives in
  the MD2017 tree only; MDUV has empty ifdef scaffolding.
- **MD2017 external microphone detection** — RJ45 hand-mic. 3 files in
  MD2017, 0 in MDUV.
- **MD9600 ST7567 monochrome LCD** — replaces the HX8353E color driver used by
  MDUV/MD2017. Selected by ifdef in the display layer.
- **MD9600 remote head interface** — detachable control head over serial.
  MDUV/MD2017 don't have a detachable head.

### Generated-code differences

- **`Core/Src/main.c`** — CubeMX-generated peripheral init. 285 lines of diff
  vs MD2017, 733 vs MD9600, because each radio wires different I²C/SPI/timer
  instances to different pins (e.g. MDUV uses I²C3, MD2017 uses I²C1).
- **`Core/Inc/main.h`** — per-board pin defines.

## Plan

### Phase 0 — snapshot the upstreams (1 hour, reversible)

Vendor the MD2017 and MD9600 zips into top-level read-only dirs as a
diff reference:

```
MD2017_firmware_upstream/    # exact unpack of OpenGD77_MD2017_20260131.zip
MD9600_firmware_upstream/    # exact unpack of OPENGD77_MD9600_20260131.zip
```

Tracked in git with no edits. Lets us diff during merging and re-sync if
upstream releases a new version.

### Phase 1 — split `Core/Src/main.c` and `Core/Inc/main.h` per platform (1–2 days)

Two viable shapes:

(a) **Per-platform files selected by Makefile.** Rename current MDUV
`Core/Src/main.c` → `Core/Src/main_mduv380.c`; add `main_md2017.c`,
`main_md9600.c` from upstream. In the Makefile filter source list by
`PLATFORM`:

```make
C_SRCS := $(filter-out Core/Src/main_%.c,$(shell find ...))
C_SRCS += Core/Src/main_$(shell echo $(PLATFORM) | tr A-Z a-z).c
```

(b) **Single `main.c` with `#if defined(PLATFORM_X)` blocks around each
peripheral init.** More merge work upfront; harder to diff against future
upstream main.c.

Recommend (a) — cleaner, easier to keep CubeMX-regenerable per platform.
Same approach for `Core/Inc/main.h` (pin defines).

### Phase 2 — fold MD2017 features into MDUV tree (3–5 days)

For each of the ~70 differing `application/` files between MDUV and MD2017:

1. `diff` MDUV's copy against MD2017's copy.
2. Identify which hunks are real MD2017-only logic (trackball, mic) vs drift
   (commented constants, formatting, copy-paste lag).
3. Move the MD2017-only logic into MDUV's copy, gated by
   `#if defined(PLATFORM_MD2017)`. Most files already have the ifdef
   structure; you're adding bodies.
4. Resolve drift by taking the newer version where both trees touched the
   same logic. The two trees were released the same day, so this is rare.

Verify by building `PLATFORM=MD2017` and bringing CI green for it.

### Phase 3 — fold MD9600 into MDUV tree (1 week)

Same process as Phase 2, plus:

1. Copy in the 7 new files (ST7567 driver + remoteHead interface). They are
   ifdef-protected at the file level already (won't compile out of MD9600
   builds).
2. Reconcile display layer where `HX8353E_display.c` (color) and
   `ST7567_display.c` (mono) are two implementations of the same interface.
   Likely fine as-is — they're selected by an outer `#if`.
3. Add MD9600 keypad map to `keyboard.c` (different physical layout).

Verify by building `PLATFORM=MD9600`.

### Phase 4 — wire up build + CI (half day)

- Extend the `ALL_VARIANTS` list in `MDUV380_firmware/Makefile`:
  `MDUV380:`, `MDUV380:UV380_PLUS_10W`, `RT84_DM1701:DM1701`, `MD2017:`,
  `MD9600:`.
- Extend the matrix in `.github/workflows/build.yml` accordingly.
- Remove `MD2017_firmware_upstream/` and `MD9600_firmware_upstream/` only
  once we're confident nothing was lost.

## Risks and caveats

- **Upstream copies, we merge** — once unified, every upstream release means a
  3-way merge across all three trees instead of an unzip. Worth it only if
  this fork's local patches (custom-data healing, themes, VFO tint, etc.) are
  intended to apply to all three radios. If only MDUV matters, unification is
  net cost.
- **`Core/Src/main.c` is CubeMX-managed** — if the maintainer regenerates it
  from `.ioc` in any tree, the per-platform-file approach (Phase 1 (a))
  preserves regeneration ergonomics for the platform you regenerate.
- **No reference binary parity** — we don't currently diff CI-built `.bin`
  output against upstream `.bin` to verify equivalence. After Phase 2/3,
  worth a one-time `objdump` + section-size comparison against upstream's
  `OpenGD77_MD2017.bin` to confirm we didn't drop anything.

## Effort estimate

- Phase 0: 1 hour
- Phase 1: 1–2 days
- Phase 2 (MD2017): 3–5 days
- Phase 3 (MD9600): ~1 week
- Phase 4: half day
- **Total: ~2 weeks** of focused work, single developer.

## Decision points

- Whether to actually do this depends on whether you want this fork's
  patches to ship on MD2017/MD9600 hardware too. If MDUV/RT3S is the only
  target, the current per-family-zip workflow is fine and this work is
  busywork.
- Re-evaluate when upstream releases a new MDUV firmware that includes
  changes worth porting — if those changes are MD2017/MD9600-relevant too,
  unification starts paying back immediately.
