#!/usr/bin/env bash
set -u

ADB="${ADB:-adb}"
ADB_TCP_PORT="${ADB_TCP_PORT:-5555}"

if ! command -v "$ADB" >/dev/null 2>&1; then
    echo "adb not found. Install android-tools-adb or set ADB=/path/to/adb."
    exit 1
fi

echo "ADB server/device list:"
"$ADB" devices -l
echo

mapfile -t DEVICES < <("$ADB" devices | awk 'NR > 1 && $2 == "device" {print $1}')

if [ "${#DEVICES[@]}" -eq 0 ]; then
    echo "No authorized Meta Quest/Oculus device found."
    echo "Connect the headset by USB, enable Developer Mode, and accept the USB debugging prompt in the headset."
    exit 1
fi

found_meta=0
for device in "${DEVICES[@]}"; do
    manufacturer="$("$ADB" -s "$device" shell getprop ro.product.manufacturer 2>/dev/null | tr -d '\r')"
    model="$("$ADB" -s "$device" shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
    device_name="$("$ADB" -s "$device" shell getprop ro.product.device 2>/dev/null | tr -d '\r')"

    label="${manufacturer} ${model} ${device_name}"
    if echo "$label" | grep -Eiq 'meta|oculus|quest|hollywood|eureka|monterey'; then
        found_meta=1
        kind="Meta Quest/Oculus"
    else
        kind="Android device"
    fi

    ip_addr="$("$ADB" -s "$device" shell ip -o -4 addr show wlan0 2>/dev/null \
        | awk '{print $4}' \
        | cut -d/ -f1 \
        | tr -d '\r' \
        | head -n 1)"

    if [ -z "$ip_addr" ]; then
        ip_addr="$("$ADB" -s "$device" shell ip route 2>/dev/null \
            | awk '/src/ {for (i=1; i<=NF; i++) if ($i == "src") print $(i+1)}' \
            | tr -d '\r' \
            | head -n 1)"
    fi

    echo "Device: $device"
    echo "  Type:  $kind"
    echo "  Model: ${manufacturer:-unknown} ${model:-unknown}"
    echo "  Name:  ${device_name:-unknown}"
    if [ -n "$ip_addr" ]; then
        echo "  WiFi IP: $ip_addr"
        echo "  ADB connect command: $ADB connect $ip_addr:$ADB_TCP_PORT"
    else
        echo "  WiFi IP: not found. Make sure the headset is connected to WiFi."
    fi

    if [[ "$device" != *.*:* ]]; then
        echo "  Enabling ADB over TCP/IP on port $ADB_TCP_PORT..."
        "$ADB" -s "$device" tcpip "$ADB_TCP_PORT" >/dev/null
    fi
    echo
done

if [ "$found_meta" -eq 0 ]; then
    echo "Warning: no connected device identified itself as Meta/Oculus/Quest."
fi
