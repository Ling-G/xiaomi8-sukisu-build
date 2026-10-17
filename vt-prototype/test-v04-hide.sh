#!/system/bin/sh
# v0.4 hidden-behaviour verification.
#
#   sh test-v04-hide.sh        insmod with the default hide_module=1
#   sh test-v04-hide.sh 0      insmod with hide_module=0 (removable, for iteration)
#
# Run from a root shell with the module *not* loaded. It loads the module,
# checks the /proc/modules, /sys/module and /dev results, runs the self test,
# holds the diagnostic node open, then starts the unmodified VT script to check
# that the 6-character discovery node is found, hidden while VT holds it, and
# restored after VT is stopped. Expected values are printed at the end.
# With hide_module=1 the module cannot be removed again: reboot to change builds.
mod=/data/local/tmp/vt_abi_probe_v04.ko
scratch=/data/local/tmp
node=/dev/vt_abi_probe
hide=${1:-}

# A hidden module never appears in /proc/modules, so the node and the sysfs
# class are the reliable "already loaded" signals. A second insmod is also
# refused by the kernel with EEXIST, because the diagnostic class name is fixed.
if [ -e /dev/vt_abi_probe ] || [ -e /sys/class/vt_abi_probe ] || grep -q '^vt_abi_probe ' /proc/modules; then
    echo "A probe instance is already active; reboot (hide_module=1) or rmmod (hide_module=0) first"
    exit 2
fi

six_char_devices() {
    for path in /dev/*; do
        name=${path#/dev/}
        case "$name" in
            *[!0-9A-Za-z]*) continue ;;
        esac
        [ "${#name}" -eq 6 ] && echo "$name"
    done
}

# /dev is maintained by ueventd, which reacts to the kernel uevent asynchronously,
# so "does the node exist yet" has to be polled instead of checked once.
# Optional second argument overrides the path being watched.
node_present_within() {
    wants=$1
    watch=${2:-$node}
    tries=0
    while [ "$tries" -lt 8 ]; do
        if [ -e "$watch" ]; then
            [ "$wants" = present ] && return 0
        else
            [ "$wants" = absent ] && return 0
        fi
        sleep 1
        tries=$((tries + 1))
    done
    return 1
}

six_char_devices > "$scratch/vt-v04-before.txt"

if [ -n "$hide" ]; then
    insmod "$mod" hide_module="$hide"
else
    insmod "$mod"
fi
load_status=$?
echo LOAD_STATUS=$load_status
if [ "$load_status" -ne 0 ]; then
    echo "insmod failed; EEXIST usually means an earlier instance is still active"
    exit "$load_status"
fi
sleep 2

six_char_devices > "$scratch/vt-v04-after.txt"
comm -13 "$scratch/vt-v04-before.txt" "$scratch/vt-v04-after.txt" > "$scratch/vt-v04-new.txt"
discovery=$(head -n 1 "$scratch/vt-v04-new.txt")
echo NEW_DEVICE_ENTRIES=$(tr '\n' ' ' < "$scratch/vt-v04-new.txt")
echo DISCOVERY_NODE=${discovery:-none}
echo KERNEL_LOG=$(dmesg | grep 'vt_abi_probe' | tail -n 2 | tr '\n' '|')

if grep -q '^vt_abi_probe ' /proc/modules; then
    echo MODULE_IN_PROC_MODULES=1
else
    echo MODULE_IN_PROC_MODULES=0
fi
if [ -e /sys/module/vt_abi_probe ]; then
    echo MODULE_IN_SYSFS=1
else
    echo MODULE_IN_SYSFS=0
fi
if node_present_within present; then
    echo DIAG_NODE_PRESENT=1
else
    echo DIAG_NODE_PRESENT=0
fi

chmod 700 "$scratch/vt_probe_test" "$scratch/vt_hold_test"
"$scratch/vt_probe_test"
echo SELFTEST_STATUS=$?
if node_present_within present; then
    echo NODE_AFTER_SELFTEST=1
else
    echo NODE_AFTER_SELFTEST=0
fi

"$scratch/vt_hold_test" &
hold_pid=$!
if node_present_within absent; then
    echo NODE_HIDDEN_WHILE_OPEN=1
else
    echo NODE_HIDDEN_WHILE_OPEN=0
fi
wait "$hold_pid"
echo HOLD_STATUS=$?
if node_present_within present; then
    echo NODE_RESTORED_AFTER_CLOSE=1
else
    echo NODE_RESTORED_AFTER_CLOSE=0
fi

if [ -n "$discovery" ] && [ -f /data/adb/VT内核-4.7.7.sh ]; then
    LD_PRELOAD= sh /data/adb/VT内核-4.7.7.sh < /dev/null > "$scratch/vt-v04-startup.txt" 2>&1 &
    vt_parent=$!
    count=0
    while kill -0 "$vt_parent" 2>/dev/null && [ "$count" -lt 12 ]; do
        grep -q 'VT驱动已安装' "$scratch/vt-v04-startup.txt" && break
        sleep 1
        count=$((count + 1))
    done
    grep -E 'VT驱动|PTE|未检测|内核版本' "$scratch/vt-v04-startup.txt"
    if grep -q 'VT驱动已安装' "$scratch/vt-v04-startup.txt"; then
        echo ORIGINAL_VT_RECOGNIZED=1
    else
        echo ORIGINAL_VT_RECOGNIZED=0
    fi
    gone=0
    tries=0
    while [ "$tries" -lt 5 ]; do
        if [ ! -e "/dev/$discovery" ]; then
            gone=1
            break
        fi
        kill -0 "$vt_parent" 2>/dev/null || break
        sleep 1
        tries=$((tries + 1))
    done
    echo DISCOVERY_NODE_HIDDEN_BY_VT=$gone
    target=$(pidof VTKernel.$vt_parent)
    [ -z "$target" ] || kill -9 "$target" 2>/dev/null
    kill -9 "$vt_parent" 2>/dev/null
    wait "$vt_parent" 2>/dev/null
    if node_present_within present "/dev/$discovery"; then
        echo DISCOVERY_NODE_RESTORED_AFTER_VT=1
    else
        echo DISCOVERY_NODE_RESTORED_AFTER_VT=0
    fi
else
    echo ORIGINAL_VT_RECOGNIZED=skipped
    echo DISCOVERY_NODE_HIDDEN_BY_VT=skipped
    echo DISCOVERY_NODE_RESTORED_AFTER_VT=skipped
fi

rmmod vt_abi_probe
echo UNLOAD_STATUS=$?

cat <<'EXPECTED'
Expected with the default hide_module=1 (sh test-v04-hide.sh):
  LOAD_STATUS=0
  NEW_DEVICE_ENTRIES=<one six-character name>, DISCOVERY_NODE=<same name>
  MODULE_IN_PROC_MODULES=0, MODULE_IN_SYSFS=0, DIAG_NODE_PRESENT=1
  SELFTEST_STATUS=0, NODE_AFTER_SELFTEST=1
  NODE_HIDDEN_WHILE_OPEN=1, HOLD_STATUS=0, NODE_RESTORED_AFTER_CLOSE=1
  ORIGINAL_VT_RECOGNIZED=1
  DISCOVERY_NODE_HIDDEN_BY_VT=1, DISCOVERY_NODE_RESTORED_AFTER_VT=1
  UNLOAD_STATUS=1: the module is unlinked, reboot to load another build
Expected with hide_module=0 (sh test-v04-hide.sh 0):
  same node and self-test results, but MODULE_IN_PROC_MODULES=1,
  MODULE_IN_SYSFS=1 and UNLOAD_STATUS=0
EXPECTED
