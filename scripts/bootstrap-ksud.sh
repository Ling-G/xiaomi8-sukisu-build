#!/system/bin/sh
# Missing backends are installed only after Android reports boot completed.
# Existing backends retain their ordinary early boot/module lifecycle.
set -eu
export PATH=/system/bin:/system/xbin
payload=/dev/dipper-ksud
target=/data/adb/ksud
expected=9f57222b06222f461bbb69b24e40a293e34708eeb7b1bbb065110651f7b9c991
phase=${1:-early}
case "$phase" in
    early|--late) ;;
    *) exit 2 ;;
esac

if [ "$phase" = early ] && [ ! -e "$target" ] && [ ! -L "$target" ]; then
    echo '<6>dipper bootstrap: missing backend deferred until boot completed' > /dev/kmsg
    exit 0
fi
if [ "$phase" = --late ] && [ "$(getprop sys.boot_completed)" != 1 ]; then
    exit 0
fi

# Never create a substitute /data directory when userdata is not mounted.
grep -q ' /data ' /proc/mounts || exit 1
umask 077
mkdir -p /data/adb
chmod 700 /data/adb
log=/data/adb/dipper-bootstrap.log
say() { echo "$(cat /proc/uptime): $*" >> "$log"; }

# Existing installations, grants, modules and user settings are left intact.
if [ -e "$target" ] || [ -L "$target" ]; then
    say 'existing backend preserved'
    exit 0
fi

actual=$(sha256sum "$payload")
[ "${actual%% *}" = "$expected" ] || { say 'payload checksum failed'; exit 1; }
say 'installing pinned official ksud 4.2.0 (UAPI 2)'
if "$payload" install >> "$log" 2>&1; then
    actual=$(sha256sum "$target")
    if [ "${actual%% *}" = "$expected" ]; then
        chown 0:0 "$target"
        chmod 700 "$target"
        chcon u:object_r:ksu_file:s0 "$target"
        say 'installation complete'
        say 'new backend: full early module stages begin on next normal boot'
        exit 0
    fi
fi
# This target did not exist on entry. Allow a failed first install to retry.
rm -f "$target"
say 'installation failed; retry on next boot'
exit 1
