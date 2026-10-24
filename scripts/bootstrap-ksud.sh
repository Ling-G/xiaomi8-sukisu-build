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
    early|--late|--manager-watch|--manager-check) ;;
    *) exit 2 ;;
esac

# Experimental repair for the exact official 4.2.1 APK only. No APK edits.
manager_apk_sha=c7f69280cf468e8415c585ff31f963d0147386831217a1e89b822afddc5f40ed
manager_lib_sha=bd58ab5cb47b27c95ee81f1ecdd0f4b645897da8e7a9281e0920b62d00eb5375
say() { echo "$(cat /proc/uptime): $*" >> /data/adb/dipper-bootstrap.log; }
hash_file() { sha256sum "$1" | cut -d ' ' -f 1; }
manager_check() (
    set -eu
    apk=$(timeout 10 cmd package path com.sukisu.ultra 2>/dev/null | sed -n 's/^package://p' | grep '/base.apk$') || exit 0
    case "$apk" in /data/app/*/base.apk) ;; *) exit 0 ;; esac
    case "$apk" in *[!a-zA-Z0-9_./=+-]*) exit 0 ;; esac
    dir=${apk%/base.apk}
    lib=$dir/lib/arm64/libksud.so
    [ -f "$apk" ] && [ ! -L "$apk" ] && [ -f "$lib" ] && [ ! -L "$lib" ] || exit 0
    [ "$(readlink -f "$apk")" = "$apk" ] && [ "$(readlink -f "$lib")" = "$lib" ] || exit 0
    [ "$(hash_file "$lib")" != "$expected" ] || exit 0
    [ "$(hash_file "$apk")" = "$manager_apk_sha" ] || { say 'manager APK not allowlisted; left unchanged'; exit 0; }
    [ "$(hash_file "$lib")" = "$manager_lib_sha" ] || { say 'manager backend unknown; left unchanged'; exit 0; }
    [ "$(hash_file "$payload")" = "$expected" ] || { say 'manager repair payload checksum failed'; exit 1; }
    backup=/data/adb/dipper-manager-compat
    mkdir -p "$backup"
    chmod 700 "$backup"
    if [ ! -e "$backup/original-libksud.so" ]; then
        cp "$lib" "$backup/original-libksud.so.tmp"
        [ "$(hash_file "$backup/original-libksud.so.tmp")" = "$manager_lib_sha" ] || exit 1
        mv "$backup/original-libksud.so.tmp" "$backup/original-libksud.so"
    fi
    [ "$(hash_file "$backup/original-libksud.so")" = "$manager_lib_sha" ] || exit 1
    tmp=$lib.dipper-tmp
    [ ! -e "$tmp" ] && [ ! -L "$tmp" ] || { say 'manager staging file exists; left unchanged'; exit 1; }
    trap 'rm -f "$tmp"' EXIT HUP INT TERM
    cp -p "$lib" "$tmp"
    context=$(ls -Zd "$lib")
    context=${context%% *}
    chcon "$context" "$tmp"
    cat "$payload" > "$tmp"
    [ "$(hash_file "$tmp")" = "$expected" ] || exit 1
    # Do not race an APK update into an obsolete installation directory.
    [ "$(timeout 10 cmd package path com.sukisu.ultra 2>/dev/null | sed -n 's/^package://p' | grep '/base.apk$')" = "$apk" ] || exit 1
    [ ! -L "$lib" ] && [ "$(hash_file "$lib")" = "$manager_lib_sha" ] || exit 1
    mv -f "$tmp" "$lib"
    printf '%s\n' "$lib" > "$backup/last-repaired-path"
    say 'official manager 4.2.1 backend repaired to pinned UAPI 2 binary'
    # Drop cached shells without clearing app data or grants.
    # Binder forwards stdout/stderr to system_server. A private /data/adb log
    # descriptor is rejected by SELinux there, so forward only /dev/null.
    if timeout 10 am force-stop com.sukisu.ultra >/dev/null 2>&1; then
        say 'manager cached shell stopped; reopen the manager'
    else
        say 'manager restart required; close and reopen manually'
    fi
)
manager_watch() (
    set -eu
    [ "$(getprop sys.boot_completed)" = 1 ] || exit 0
    [ ! -e /data/adb/dipper-manager-compat.disable ] || exit 0
    mkdir /dev/dipper-manager-compat.lock 2>/dev/null || exit 0
    trap 'rmdir /dev/dipper-manager-compat.lock' EXIT HUP INT TERM
    previous=
    while [ ! -e /data/adb/dipper-manager-compat.disable ]; do
        state=$(timeout 10 cmd package path com.sukisu.ultra 2>/dev/null || true)
        if [ "$state" != "$previous" ]; then
            if /system/bin/sh /dev/dipper-bootstrap.sh --manager-check; then
                previous=$state
            else
                say 'manager repair failed; retry later'
            fi
        fi
        sleep 60
    done
)
if [ "$phase" = --manager-check ]; then
    [ "$(getprop sys.boot_completed)" = 1 ] || exit 0
    [ ! -e /data/adb/dipper-manager-compat.disable ] || exit 0
    manager_check
    exit 0
fi
if [ "$phase" = --manager-watch ]; then
    manager_watch
    exit 0
fi

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

# Start only after Android boot completed; never block the init boot action.
if [ "$phase" = --late ]; then
    /system/bin/sh /dev/dipper-bootstrap.sh --manager-watch </dev/null >/dev/null 2>&1 &
fi

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
