"""Restore only apk-research-owned Android HTTPS settings after a stopped session.

A previous process may disappear before its normal cleanup. The managed
proxy port and dedicated NAT chain identify our own settings; unrelated
proxy addresses and NAT rules must remain untouched.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass

DEVICE_PROXY_PORT = 38887
DEVICE_ROUTE_CHAIN = "APKRS_HTTPS32"
BASELINE_FILE = "/data/local/tmp/apk-research/https-proxy-baseline"


class NetworkRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class NetworkRecovery:
    needed: bool
    proxy_restored: bool
    route_removed: bool
    proxy_after: str
    details: str


def _remote_script(adb, serial: str, script: str, *, timeout: float = 20.0) -> str:
    return adb.shell_output(
        serial, "sh -c " + shlex.quote(script), timeout=timeout
    )


def restore_inactive_https_network(adb, serial: str) -> NetworkRecovery:
    """Recover abandoned research settings when NO research session is active.

    Never call while the HTTPS analyzer is running. The caller enforces this.
    Check ownership via the exact localhost proxy port and the named chain.
    This operation does not reset Wi-Fi, app data, DNS or foreign proxy values.
    """
    script = r"""
set -u
CHAIN=APKRS_HTTPS32
BASE=/data/local/tmp/apk-research/https-proxy-baseline
ROOT=/data/local/tmp/apk-research/https-route32
CURRENT=$(settings get global http_proxy 2>/dev/null | tr -d '\r')
NEEDED=0
PROXY_CHANGED=0
ROUTE_REMOVED=0

if [ "$CURRENT" = "127.0.0.1:38887" ]; then
  NEEDED=1
  PREVIOUS=:0
  if [ -f "$BASE" ]; then
    VALUE=$(cat "$BASE" 2>/dev/null | tr -d '\r\n')
    case "$VALUE" in
      ""|"null"|"127.0.0.1:38887") ;;
      *) PREVIOUS=$VALUE ;;
    esac
  fi
  settings put global http_proxy "$PREVIOUS" || exit 31
  NEW=$(settings get global http_proxy 2>/dev/null | tr -d '\r')
  if [ "$NEW" = "127.0.0.1:38887" ]; then exit 32; fi
  PROXY_CHANGED=1
else
  NEW=$CURRENT
fi

if iptables -t nat -S OUTPUT 2>/dev/null | grep -F -- "-j $CHAIN" >/dev/null; then
  NEEDED=1
  iptables -t nat -S OUTPUT 2>/dev/null | grep -F -- "-j $CHAIN" |
    while read -r TYPE TABLE REST; do
      if [ "$TYPE" = "-A" ] && [ "$TABLE" = "OUTPUT" ]; then
        set -- $REST
        iptables -t nat -D OUTPUT "$@" || exit 33
      fi
    done
fi
if iptables -t nat -S "$CHAIN" >/dev/null 2>&1; then
  NEEDED=1
  iptables -t nat -F "$CHAIN" || exit 34
  iptables -t nat -X "$CHAIN" || exit 35
fi
if iptables -t nat -S OUTPUT 2>/dev/null | grep -F -- "-j $CHAIN" >/dev/null; then
  exit 36
fi
if iptables -t nat -S "$CHAIN" >/dev/null 2>&1; then exit 37; fi
ROUTE_REMOVED=1

# No arbitrary PID termination: a stale pid could now belong to other code.
if [ -f "$ROOT/route.pid" ]; then
  PID=$(cat "$ROOT/route.pid" 2>/dev/null)
  case "$PID" in
    ""|*[!0-9]*) ;;
    *)
      if [ -r "/proc/$PID/cmdline" ] &&
         tr '\000' ' ' < "/proc/$PID/cmdline" |
            grep -F -q 'apk-research-https-route'; then
        kill "$PID" 2>/dev/null || true
      fi
      ;;
  esac
fi
rm -rf "$ROOT"
# Do not clear a recovery checkpoint unless its value is no longer active.
if [ "$NEW" != "127.0.0.1:38887" ]; then rm -f "$BASE"; fi

printf 'APKRS_RECOVERY_OK needed=%s proxy_restored=%s route_removed=%s\n' \
  "$NEEDED" "$PROXY_CHANGED" "$ROUTE_REMOVED"
"""
    try:
        output = _remote_script(adb, serial, script, timeout=30.0)
    except Exception as exc:
        raise NetworkRecoveryError(
            "Не удалось проверить и восстановить сеть Android: " + str(exc)
        ) from exc
    if "APKRS_RECOVERY_OK " not in output:
        raise NetworkRecoveryError(
            "Android не подтвердил восстановление сетевых настроек"
        )

    # Only remove the reverse port allocated by our own HTTPS analyzer.
    if "needed=1" in output:
        try:
            adb.remove_reverse_tcp(serial, DEVICE_PROXY_PORT)
        except Exception:
            # Stale reverse entry may already be absent.
            pass
    actual = adb.shell_output(
        serial, "settings", "get", "global", "http_proxy"
    ).strip()
    if actual == "127.0.0.1:38887":
        raise NetworkRecoveryError(
            "В Android остался служебный HTTPS-прокси после восстановления"
        )
    return NetworkRecovery(
        needed="needed=1" in output,
        proxy_restored="proxy_restored=1" in output,
        route_removed="route_removed=1" in output,
        proxy_after=actual,
        details=output.strip(),
    )
