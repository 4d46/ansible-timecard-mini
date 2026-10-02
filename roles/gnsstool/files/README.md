# gnsstool

Query and configure the u-blox GNSS chip via I2C, without interfering with
TimeBeat which owns the UART port.

Installed and managed by Ansible to `/opt/gnsstool/`.

---

## Commands

### `gnsstool status`

Overall status: fix type, position, satellite count, UTC time and accuracy.

```
Fix type:    3D fix
Satellites:  14 used in fix
Position:    51.123456°N  1.234567°W  ±1.2m
Altitude:    42.3m MSL  ±1.8m
PDOP:        0.92
UTC time:    2026-05-14 14:23:01  ±18ns
```

### `gnsstool satellites`

Constellation summary and per-satellite signal strength (SNR, dB-Hz).

```
--- Constellation Summary ---
  Constellation  SVs  Avg SNR  Strong  Fair  Weak
  ------------------------------------------------
  BeiDou           4     38.0       3     1     0
  GPS              8     42.1       6     2     0
  GLONASS          3     38.4       2     1     0
  Galileo          3     40.2       3     0     0

--- Satellites (18 tracked) ---
  Satellite       Elev    Az   SNR   Used
  ----------------------------------------
  GPS/07           72°  134°    47    yes
  GPS/09           61°  289°    45    yes
  ...

  SNR guide: <20 weak | 20-34 fair | 35-44 good | >=45 excellent
```

### `gnsstool platform`

Show the current dynamic platform model and what it means for timing accuracy.

```
Platform mode:  Stationary  (CFG-NAVSPG-DYNMODEL = 2)

The chip is in stationary mode: velocity is constrained to zero and zero-dynamics
are assumed. This is the recommended configuration for a fixed timing antenna.
Expected PPS accuracy: tens of nanoseconds.
```

### `gnsstool platform set stationary`

Switch to stationary mode for best timing accuracy with a fixed antenna.

```
Platform mode set to: Stationary

Note: change is RAM-only and will be lost on chip reset or power cycle.
TimeBeat may override this on restart — check its GNSS configuration.
```

### `gnsstool platform set portable`

Revert to the factory default portable mode.

### `gnsstool elevation`

Show the current minimum elevation mask, and preview how many of the satellites
currently tracked each mask would exclude. The preview reflects the sky right now —
run it at different times of day before choosing a value.

Example output (satellite figures from a real snapshot; the current mask value is illustrative):

```
Elevation mask:  5°  (CFG-NAVSPG-INFIL_MINELEV = 5)

Satellites below the mask are still tracked but not used in the navigation/timing solution.

Currently tracked: 21   used in fix: 20

--- Tracked satellites excluded at each mask ---
   Mask  Excluded  Remaining
  --------------------------
     5°         0         21  <- current
    10°         3         18
    15°         3         18
    20°         6         15
    25°         7         14

--- Low satellites (below 25°) ---
  Satellite       Elev    Az   SNR   Used
  ----------------------------------------
  GPS/21            6°   20°    29    yes
  Galileo/08        6°  239°    14    yes
  GPS/04            9°  292°    36    yes
  ...
```

### `gnsstool elevation set <degrees>`

Set the minimum elevation (0–90°). Satellites below it are ignored in the solution.

```
Elevation mask set to: 15°

Note: change is RAM-only and will be lost on chip reset or power cycle.
Verify with: gnsstool elevation
```

---

## Timing accuracy and platform mode

The MAX-F10S is a standard precision receiver, not a dedicated timing receiver.
It does not support survey-in or a fixed-position time-only mode (those are features
of receivers like the ZED-F9T). Instead, timing accuracy is governed by the
dynamic platform model (CFG-NAVSPG-DYNMODEL):

**Portable (default, value 0)** — solves for position and time independently each
navigation epoch. Position uncertainty feeds directly into timing uncertainty.
Typical PPS accuracy: hundreds of nanoseconds.

**Stationary (value 2)** — constrains velocity to zero and applies zero-dynamics
assumptions, allowing the position estimate to converge more accurately. The u-blox
integration manual describes this as "Used in timing applications (antenna must be
stationary)." Typical PPS accuracy: tens of nanoseconds.

The platform mode is set in RAM and is lost on chip reset. If TimeBeat is
configured to set the dynamic model itself, its setting will take effect on restart.

---

## Timing accuracy and elevation mask

The elevation mask (CFG-NAVSPG-INFIL_MINELEV) stops satellites close to the horizon
being used in the solution. Signal strength is not the reason: a low satellite can
have an excellent SNR and still be a poor timing source, because:

- **Troposphere** — a low signal crosses far more of the lower atmosphere. The delay
  scales roughly as 1/sin(elevation): ~2.3 m at the zenith, ~10 m at 15°, ~25 m at 5°.
  The receiver removes most of it with a standard model, but the residual error scales
  the same way. Range error is time error (1 m ≈ 3.3 ns), so it feeds the PPS directly.
- **Ionosphere** — also worse at low elevation. The MAX-F10S is dual-band (L1 + L5) and
  can largely cancel this for satellites tracked on both bands; the troposphere affects
  both bands equally, so it is the error the mask mainly addresses.
- **Multipath** — low-angle signals reflect off the ground and nearby buildings far more.

The trade-off is geometry: low satellites spread the sky coverage, which helps the
solution. 10–15° is the usual range for timing; going much higher starves the receiver.

The mask is set in RAM and is lost on chip reset.

---

## Experimenting one setting at a time

Both settings are RAM-only, so each experiment reverts itself on a chip power cycle.
Change one thing, let it run, compare.

1. **Baseline** — capture the starting state at a few times of day:
   ```bash
   gnsstool platform
   gnsstool elevation
   gnsstool satellites > ~/gnss-baseline-$(date +%F-%H%M).txt
   ```
   Note TimeBeat's PPS offset/jitter and gnsstrack's position spread over the same period.
2. **Change one setting**, then confirm it took:
   ```bash
   gnsstool platform set stationary && gnsstool platform
   ```
3. **Let it run for about a day** — satellite geometry repeats roughly every 12–24 hours,
   so a short window can mislead.
4. **Compare** against the baseline, then move to the next setting:
   ```bash
   gnsstool elevation set 15 && gnsstool elevation
   ```
5. **Revert** a setting by setting it back to the value shown in the baseline
   (e.g. `gnsstool platform set portable`, `gnsstool elevation set 5`), or power-cycle the chip.

After a `sudo systemctl restart timebeat`, re-run `gnsstool platform` and
`gnsstool elevation` to check whether TimeBeat reconfigures the chip on startup.

---

## Cleanup

```bash
sudo rm -rf /opt/gnsstool
sudo rm /usr/local/bin/gnsstool
```

Or disable in Ansible (`gnsstool_enabled: false` in vars.yml) and run `make deploy`.
