#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script reads the transformations and button states from the Oculus Quest controller using ADB.
main script from: https://github.com/rail-berkeley/oculus_reader/
Optimized by: Moniruzzaman Akash
"""
import numpy as np
import threading
import time
import os, subprocess
from ppadb.client import Client as AdbClient
import sys

def eprint(*args, **kwargs):
    RED = "\033[1;31m"  
    sys.stderr.write(RED)
    print(*args, file=sys.stderr, **kwargs)
    RESET = "\033[0;0m"
    sys.stderr.write(RESET)


def parse_buttons(text):
    split_text = text.split(',')
    buttons = {}
    if 'R' in split_text: # right hand if available
        split_text.remove('R') # remove marker
        buttons.update({'A': False,
                        'B': False,
                        'RThU': False, # indicates that right thumb is up from the rest position
                        'RJ': False, # joystick pressed
                        'RG': False, # boolean value for trigger on the grip (delivered by SDK)
                        'RTr': False # boolean value for trigger on the index finger (delivered by SDK)
                        })
        # besides following keys are provided:
        # 'rightJS' / 'leftJS' - (x, y) position of joystick. x, y both in range (-1.0, 1.0)
        # 'rightGrip' / 'leftGrip' - float value for trigger on the grip in range (0.0, 1.0)
        # 'rightTrig' / 'leftTrig' - float value for trigger on the index finger in range (0.0, 1.0)

    if 'L' in split_text: # left hand accordingly
        split_text.remove('L') # remove marker
        buttons.update({'X': False, 'Y': False, 'LThU': False, 'LJ': False, 'LG': False, 'LTr': False})
    for key in buttons.keys():
        if key in list(split_text):
            buttons[key] = True
            split_text.remove(key)
    for elem in split_text:
        split_elem = elem.split(' ')
        if len(split_elem) < 2:
            continue
        key = split_elem[0]
        value = tuple([float(x) for x in split_elem[1:]])
        buttons[key] = value
    return buttons

class FPSCounter:
    def __init__(self):
        current_time = time.time()
        self.start_time_for_display = current_time
        self.last_time = current_time
        self.x = 5  # displays the frame rate every X second
        self.time_between_calls = []
        self.elements_for_mean = 50

    def getAndPrintFPS(self, print_fps=True):
        current_time = time.time()
        self.time_between_calls.append(1.0/(current_time - self.last_time + 1e-9))
        if len(self.time_between_calls) > self.elements_for_mean:
            self.time_between_calls.pop(0)
        self.last_time = current_time
        frequency = np.mean(self.time_between_calls)
        if (current_time - self.start_time_for_display) > self.x and print_fps:
            print("Frequency: {}Hz".format(int(frequency)))
            self.start_time_for_display = current_time
        return frequency
    
  
class OculusReader:
    def __init__(self,
            ip_address=None,
            port = 5555,
            APK_name='com.rail.oculus.teleop',
            print_FPS=False,
            run=True
        ):
        self.running = False
        self.last_transforms = {}
        self.last_buttons = {}
        self.prev_transforms = {}
        self._lock = threading.Lock()
        self.tag = 'wE9ryARX'

        self.ip_address = ip_address
        self.port = port
        self.APK_name = APK_name
        self.print_FPS = print_FPS
        if self.print_FPS:
            self.fps_counter = FPSCounter()

        self.device = self.get_device()
        self.install(verbose=False)
        if run:
            self.run()

    def __del__(self):
        self.stop()

    def run(self):
        self.running = True
        self.device.shell('am start -n "com.rail.oculus.teleop/com.rail.oculus.teleop.MainActivity" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER')
        self.thread = threading.Thread(target=self.device.shell, args=("logcat -T 0", self.read_logcat_by_line))
        self.thread.start()

        self.ping_thread = threading.Thread(target=self.keep_adb_alive, daemon=True)
        self.ping_thread.start()

    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join()
        if hasattr(self, 'ping_thread'):
            self.ping_thread.join()

    @staticmethod
    def _is_network_serial(serial):
        host = serial.split(':', 1)[0]
        return host.count('.') == 3

    @staticmethod
    def _ip_cache_path():
        return os.path.join(os.path.expanduser('~'), '.cache', 'spot_teleop', 'meta_quest_ip')

    @classmethod
    def _cached_ip(cls):
        try:
            with open(cls._ip_cache_path(), 'r', encoding='utf-8') as f:
                ip = f.read().strip()
            if ip.count('.') == 3:
                return ip
        except OSError:
            pass
        return None

    @classmethod
    def _remember_ip(cls, ip_address):
        if ip_address is None or ip_address.count('.') != 3:
            return
        path = cls._ip_cache_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(ip_address + '\n')
        except OSError:
            pass

    @staticmethod
    def _extract_device_ip(device):
        try:
            output = device.shell('ip -o -4 addr show wlan0')
            for line in output.splitlines():
                fields = line.replace('\r', '').split()
                if len(fields) >= 4 and '/' in fields[3]:
                    ip = fields[3].split('/')[0]
                    if ip.count('.') == 3:
                        return ip
        except Exception:
            pass

        try:
            output = device.shell('ip route')
            for line in output.splitlines():
                parts = line.replace('\r', '').split()
                if 'src' in parts:
                    ip = parts[parts.index('src') + 1]
                    if ip.count('.') == 3:
                        return ip
        except Exception:
            pass

        return None

    def _print_usb_setup_help(self):
        eprint('Meta Quest not found on WiFi.')
        eprint('  1. Plug the headset in with USB.')
        eprint('  2. Put it on and allow the USB debugging prompt.')
        eprint('  3. Keep it on the same WiFi as this computer.')
        eprint('Press Enter to retry. Teleop switches to WiFi, then you can unplug.')
        eprint('Know the IP? Use --meta-quest-ip <ip>.')

    @staticmethod
    def _prompt_usb_retry():
        """Ask the user to plug the headset in over USB, then retry.

        Returns False when there is no terminal to ask on, or the user gives up.
        """
        if sys.stdin is None or not sys.stdin.isatty():
            return False
        try:
            input('Plug in the headset, then press Enter to retry (Ctrl+C to quit): ')
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        return True

    def get_network_device(self, client, retry=0):
        try:
            client.remote_connect(self.ip_address, self.port)
        except RuntimeError:
            os.system('adb devices')
            client.remote_connect(self.ip_address, self.port)
        device = client.device(self.ip_address + ':' + str(self.port))

        if device is None:
            if retry == 1:
                os.system('adb tcpip ' + str(self.port))
            if retry >= 2:
                eprint('No Meta Quest answered at ' + self.ip_address + ':' + str(self.port) + '.')
                return None
            return self.get_network_device(client=client, retry=retry + 1)
        self._remember_ip(self.ip_address)
        return device

    def get_usb_device(self, client):
        try:
            devices = client.devices()
        except RuntimeError:
            os.system('adb devices')
            devices = client.devices()
        for device in devices:
            if device.serial.count('.') < 3:
                return device
        eprint('No headset on USB. Check `adb devices`.')
        return None

    def _find_wifi_device(self, client, show_help=True):
        """One attempt at reaching the headset. Returns None instead of exiting."""
        try:
            devices = client.devices()
        except RuntimeError:
            os.system('adb devices')
            devices = client.devices()

        for device in devices:
            if self._is_network_serial(device.serial):
                self.ip_address = device.serial.split(':', 1)[0]
                self._remember_ip(self.ip_address)
                print(f'Using Meta Quest wireless ADB device at {self.ip_address}:{self.port}.')
                return device

        cached_ip = self._cached_ip()
        if cached_ip is not None:
            print(f'Trying cached Meta Quest WiFi IP: {cached_ip}:{self.port}...')
            try:
                client.remote_connect(cached_ip, self.port)
                device = client.device(f'{cached_ip}:{self.port}')
            except RuntimeError:
                device = None
            if device is not None:
                self.ip_address = cached_ip
                print(f'Connected to Meta Quest over WiFi at {self.ip_address}:{self.port}.')
                return device
            eprint(f'Saved IP {cached_ip} did not answer.')

        usb_device = None
        for device in devices:
            if not self._is_network_serial(device.serial):
                usb_device = device
                break

        if usb_device is None:
            if show_help:
                self._print_usb_setup_help()
            else:
                eprint('Still no headset found.')
            return None

        ip_address = self._extract_device_ip(usb_device)
        if ip_address is None:
            eprint('Headset is on USB but has no WiFi address. Connect it to WiFi.')
            return None

        self.ip_address = ip_address
        print(f'Found Meta Quest WiFi IP via USB: {self.ip_address}')
        print(f'Enabling wireless ADB on port {self.port}...')
        result = subprocess.run(
            ['adb', '-s', usb_device.serial, 'tcpip', str(self.port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            eprint('Could not switch the headset to wireless ADB.')
            eprint(result.stderr.strip() or result.stdout.strip())
            return None

        time.sleep(1.0)
        print(f'Connecting to Meta Quest over WiFi at {self.ip_address}:{self.port}...')
        return self.get_network_device(client)

    def get_auto_wifi_device(self, client):
        show_help = True
        while True:
            device = self._find_wifi_device(client, show_help=show_help)
            if device is not None:
                return device
            show_help = False
            if not self._prompt_usb_retry():
                raise RuntimeError('Meta Quest not connected.')

    def get_device(self):
        # Default is "127.0.0.1" and 5037
        client = AdbClient(host="127.0.0.1", port=5037)
        if self.ip_address is not None:
            device = self.get_network_device(client)
            if device is not None:
                return device
            eprint(f'Headset not reachable at {self.ip_address}. Searching instead...')
            self.ip_address = None
        return self.get_auto_wifi_device(client)

    def install(self, APK_path=None, verbose=True, reinstall=False):
        try:
            installed = self.device.is_installed(self.APK_name)
            if not installed or reinstall:
                if APK_path is None:
                    apk_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'APK')
                    APK_path = os.path.join(apk_dir, 'OculusTeleop-debug.apk')
                    if not os.path.exists(APK_path):
                        APK_path = os.path.join(apk_dir, 'teleop-debug.apk')
                success = self.device.install(APK_path, test=True, reinstall=reinstall)
                installed = self.device.is_installed(self.APK_name)
                if installed and success:
                    print('APK installed successfully.')
                else:
                    eprint('APK install failed.')
            elif verbose:
                print('APK is already installed.')
        except RuntimeError:
            eprint('Headset found but not authorized. Put it on and allow access.')
            exit(1)

    def uninstall(self, verbose=True):
        try:
            installed = self.device.is_installed(self.APK_name)
            if installed:
                success = self.device.uninstall(self.APK_name)
                installed = self.device.is_installed(self.APK_name)
                if not installed and success:
                    print('APK uninstall finished.')
                    print('Please verify if the app disappeared from the list as described in "UNINSTALL.md".')
                    print('For the resolution of this issue, please follow https://github.com/Swind/pure-python-adb/issues/71.')
                else:
                    eprint('APK uninstall failed')
            elif verbose:
                print('APK is not installed.')
        except RuntimeError:
            eprint('Headset found but not authorized. Put it on and allow access.')
            exit(1)

    @staticmethod
    def process_data(string):
        try:
            transforms_string, buttons_string = string.split('&')
        except ValueError:
            return None, None
        split_transform_strings = transforms_string.split('|')
        transforms = {}
        for pair_string in split_transform_strings:
            transform = np.empty((4,4))
            pair = pair_string.split(':')
            if len(pair) != 2:
                continue
            left_right_char = pair[0] # is r or l
            transform_string = pair[1]
            values = transform_string.split(' ')
            c = 0
            r = 0
            count = 0
            for value in values:
                if not value:
                    continue
                transform[r][c] = float(value)
                c += 1
                if c >= 4:
                    c = 0
                    r += 1
                count += 1
            if count == 16:
                transforms[left_right_char] = transform
        buttons = parse_buttons(buttons_string)
        return transforms, buttons

    def extract_data(self, line):
        output = ''
        if self.tag in line:
            try:
                output += line.split(self.tag + ': ')[1]
            except ValueError:
                pass
        return output

    def get_transformations_and_buttons(self):
        with self._lock:
            # if the last transformations are the same as the previous ones(potential connection lost), return empty dicts
            if 'l' in self.last_transforms and 'l' in self.prev_transforms:
                if np.allclose(self.last_transforms['l'], self.prev_transforms['l'], atol=1e-6):
                    self.prev_transforms = self.last_transforms.copy()
                    return {}, {}
            self.prev_transforms = self.last_transforms.copy()
            return self.last_transforms, self.last_buttons

    def read_logcat_by_line(self, connection):
        file_obj = connection.socket.makefile()
        while self.running:
            try:
                line = file_obj.readline().strip()
                data = self.extract_data(line)
                if data:
                    transforms, buttons = OculusReader.process_data(data)
                    with self._lock:
                        self.last_transforms, self.last_buttons = transforms, buttons
                    if self.print_FPS:
                        self.fps_counter.getAndPrintFPS()
            except UnicodeDecodeError:
                pass
                
        file_obj.close()
        connection.close()

    # Background keep-alive ping thread
    def keep_adb_alive(self):
        while self.running:
            try:
                self.device.shell("echo 'ping'")
                self.device.shell("svc power stayon true")

            except Exception as e:
                eprint("ADB ping error:", e)
            time.sleep(20)  # every 20 seconds

def get_connecteed_device_ip():
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        for device in client.devices():
            if OculusReader._is_network_serial(device.serial):
                return device.serial.split(':', 1)[0]
            ip = OculusReader._extract_device_ip(device)
            if ip is not None:
                return ip
        print("Has no access! Please connect the device via USB and allow access.")
        return None
    except Exception as e:
        eprint("Error getting connected device IP:", e)
        return None

def main():
    # Optional: Set your device IP if using wireless ADB
    # IP_ADDRESS = None # Use meta quest IP e.g "192.168.1.54" if you want to control over wifi.
    IP_ADDRESS = get_connecteed_device_ip() # Use None if connected over USB

    oculus_reader = OculusReader(ip_address=IP_ADDRESS)

    try:
        while True:
            time.sleep(0.1)
            poses, buttons = oculus_reader.get_transformations_and_buttons()
            print(poses)
            print(buttons)
    except KeyboardInterrupt:
        print("Interrupted by user. Stopping...")
        oculus_reader.stop()


if __name__ == '__main__':
    main()
