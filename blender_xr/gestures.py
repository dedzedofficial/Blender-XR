# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional finger input. No Blender dependency; loss of input never commits edits."""
import json
import math
import secrets
import socket
import time


class HoldGesture:
    def __init__(self, delay=0.7):
        self.delay = delay
        self.start = None
        self.fired = False

    def update(self, held, now):
        if not held:
            self.start = None
            self.fired = False
            return False
        if self.start is None:
            self.start = now
        if not self.fired and now - self.start >= self.delay:
            self.fired = True
            return True
        return False


class HandBridge:
    """Authenticated loopback-only UDP; both hands must be fresh and released to arm."""
    def __init__(self, port=39540, clock=time.monotonic):
        self.clock = clock
        self.key = secrets.token_hex(16)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('127.0.0.1', port))
            self.socket.setblocking(False)
        except Exception:
            self.socket.close()
            raise
        self.port = self.socket.getsockname()[1]
        self.last = float('-inf')
        self.sequence = -1
        self.hands = None
        self.armed = False
        self.pinched = [False, False]
        self.gripped = [False, False]

    def accept(self, payload, address):
        if address[0] != '127.0.0.1' or len(payload) > 2048:
            return False
        try:
            data = json.loads(payload)
            seq = data['seq']
            if data['v'] != 1 or data['key'] != self.key:
                return False
            if type(seq) is not int or seq <= self.sequence:
                return False
            hands = data['hands']
            if not isinstance(hands, list) or len(hands) != 2:
                return False
            validated = []
            for hand in hands:
                # Estimated skeletal poses are controller buttons, not tracked fingers.
                if hand['tracked'] is not True or hand['level'] not in ('partial', 'full'):
                    raise ValueError('No tracked fingers')
                pinch, curl = hand['pinch'], hand['curl']
                if (type(pinch) not in (int, float) or type(curl) not in (int, float)
                        or not math.isfinite(pinch) or not math.isfinite(curl)
                        or not 0 <= pinch <= 0.3 or not 0 <= curl <= 1):
                    raise ValueError('Invalid hand measurements')
                validated.append((pinch, curl))
            self.hands = validated
            self.sequence = seq
            self.last = self.clock()
            return True
        except (KeyError, ValueError, TypeError, UnicodeDecodeError):
            return False

    def read(self):
        # Bounded drain so a noisy sender cannot monopolize Blender's modal timer.
        for _ in range(64):
            try:
                payload, address = self.socket.recvfrom(2049)
            except BlockingIOError:
                break
            self.accept(payload, address)
        if self.hands is None or self.clock() - self.last > 0.25:
            self.armed = False
            self.pinched = [False, False]
            self.gripped = [False, False]
            return None
        if not self.armed:
            if not all(p > 0.035 and c < 0.45 for p, c in self.hands):
                return None
            self.armed = True
        for i, (pinch, curl) in enumerate(self.hands):
            self.pinched[i] = pinch < (0.035 if self.pinched[i] else 0.025)
            self.gripped[i] = curl > (0.45 if self.gripped[i] else 0.75)
        return tuple((float(p), float(g)) for p, g in zip(self.pinched, self.gripped))

    def close(self):
        self.socket.close()
