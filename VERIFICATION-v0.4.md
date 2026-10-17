# v0.4 verification record

Date: 2026-10-17. Device: Xiaomi Mi 8 (dipper), MIUI Android 10, kernel `4.9.186-perf-g10af704`.

Build: [run #10 / 39041250572](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/39041250572), commit `4828a68`, all job steps successful.

## Artifact check (local, against the authoritative 11,641-symbol table)

| item | value |
| --- | --- |
| module SHA256 | `28bd95b8c51b4e7fce41e00ace09a9a84087af5b6f875081fd349a1b2290f54e` |
| module size | 267,376 bytes |
| machine | AArch64 ELF64 little-endian |
| vermagic | `4.9.186-perf-g10af704 SMP preempt mod_unload modversions aarch64` |
| `module_layout` CRC | `0x2ee5b3bb` |
| versioned symbols | 41 |
| required imports | 40 |
| stale imports (`misc_*`) | none |
| imports differing from the static prediction | none |
| unexpected imports (`__list_del_entry` etc.) | none |

The 40 imports match what `derive-imports.py` derives from the source, and every CRC matched.

## On-device verification (two rounds, unmodified `VT内核-4.7.7.sh`)

| check | `hide_module=0` | `hide_module=1` |
| --- | --- | --- |
| module in `/proc/modules` | yes | **no** |
| module in `/sys/module` | yes | **no** |
| `/dev/vt_abi_probe` present | yes | yes |
| native self test | `SELFTEST_STATUS=0` | `SELFTEST_STATUS=0` |
| node hidden while open | `NODE_HIDDEN_WHILE_OPEN=1` | `NODE_HIDDEN_WHILE_OPEN=1` |
| node restored after close | yes | yes |
| original VT recognises driver | `ORIGINAL_VT_RECOGNIZED=1` | `ORIGINAL_VT_RECOGNIZED=1` |
| discovery node hidden by VT | `DISCOVERY_NODE_HIDDEN_BY_VT=1` | `DISCOVERY_NODE_HIDDEN_BY_VT=1` |
| discovery node restored after VT | `DISCOVERY_NODE_RESTORED_AFTER_VT=1` | `DISCOVERY_NODE_RESTORED_AFTER_VT=1` |
| `rmmod vt_abi_probe` | `UNLOAD_STATUS=0` | `UNLOAD_STATUS=1`, `ENOENT` |

The second round's `rmmod` failure is the intended behaviour: the module unlinks itself from the module list, so `delete_module` cannot find it. `dmesg` records `vt_abi_probe: unlinked from the module list; rmmod needs a reboot`.

Nodes use a fresh random six-character name on each load (`MlLhYV` in round one, `vjHkNL` in round two), matching the recovered `get_rand_str` (62-character table, length 6, `sizeof(charset)-1` modulus).

## Notes

- The kernel prints `CHRDEV "vt_abi_probe" major number 205 goes below the dynamic allocation range` on load. It is harmless here: the node is created, read, hidden and restored as expected.
- `/dev` is a tmpfs maintained by `ueventd` (`CONFIG_DEVTMPFS` is off); measured latency from `insmod` to both nodes appearing is about 18 ms.
- Hardware breakpoints, tracking and the full PTE interface remain unimplemented. Recognition does not imply those work.
