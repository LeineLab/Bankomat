import RPi.GPIO as GPIO
import time
import datetime
import os
import threading


class CoinPulse:
    _last_pulse = 0
    _pulses = 0
    _enabled = True
    _value_for_pulses = {}
    _logfile = None

    def _edgeCallback(self, channel):
        now = time.time()
        # GPIO.BOTH doesn't tell us which edge fired; the current level does:
        # HIGH means we just saw the pulse end (rising), LOW means it just
        # started (falling).
        if GPIO.input(self._pulse_pin):
            self._onRising(now)
        else:
            self._onFalling(now)

    def _onFalling(self, now):
        with self._lock:
            self._pending_falling = now

    def _onRising(self, now):
        log_args = None
        with self._lock:
            falling = self._pending_falling
            self._pending_falling = None
            if falling is None:
                # No matching pulse start on record (e.g. right after
                # startup) - can't validate width, so ignore.
                return
            width = now - falling
            pause = (
                (falling - self._last_valid_rising)
                if self._last_valid_rising
                else None
            )
            if width < self._min_pulse_width or width > self._max_pulse_width:
                log_args = (self._pulses, self._enabled, width, pause, "reject_width")
            elif pause is not None and pause < self._min_pause:
                log_args = (self._pulses, self._enabled, width, pause, "reject_pause")
            else:
                # Capture the enabled state *before* it changes, so the log
                # can reveal pulses that arrive while the input should have
                # been blocked (a strong ghost-pulse indicator).
                was_enabled = self._enabled
                self._last_valid_rising = now
                self._pulses += 1
                self._last_pulse = now
                # Arm the delayed inhibit on the *first* pulse of a coin
                # only; later pulses of the same train don't reset it. A
                # fixed delay (not "N ms after the last pulse") is what lets
                # the coin physically commit before we fake the exit
                # blocked, without requiring the whole multi-pulse train to
                # finish first. Gate on _inhibit_scheduled, NOT on
                # _inhibit_timer being None: the timer object itself is
                # cleared once it fires (see _delayedInhibit), so using it
                # as the arming gate would let every later pulse in the same
                # train re-arm a fresh timer - a real bug seen in the field
                # (2026-08-17): three separate inhibit_write events for one
                # 3-pulse coin instead of one.
                if not self._inhibit_scheduled:
                    self._inhibit_scheduled = True
                    epoch = self._epoch
                    self._inhibit_timer = threading.Timer(
                        self._inhibit_delay, self._delayedInhibit, args=(epoch,)
                    )
                    self._inhibit_timer.daemon = True
                    self._inhibit_timer.start()
                log_args = (self._pulses, was_enabled, width, pause, "ok")
        self._log(*log_args)

    def _delayedInhibit(self, epoch):
        with self._lock:
            if epoch != self._epoch:
                # Superseded by an enable()/inhibit() since this was armed.
                return
            self._inhibit_timer = None
            self._enabled = False
        self._writeInhibitPin(1)

    def _writeInhibitPin(self, value):
        # Every write to this pin is a suspected noise source coupling onto
        # the adjacent pulse line (see coin_log analysis, 2026-08-17) -
        # timestamp it in the same log so it can be correlated directly
        # against rejected/accepted pulses instead of just inferred.
        GPIO.output(self._inhibit_pin, value)
        if self._logfile is not None:
            self._logfile.write(
                '"%s";%f;%d;%d;inhibit_write=%d;;\n'
                % (
                    datetime.datetime.now().strftime("%d.%m.%y %H:%M:%S.%f"),
                    time.time(),
                    self._pulses,
                    1 if self._enabled else 0,
                    value,
                )
            )

    def _log(self, pulses, was_enabled, width, pause, status):
        # Runs in the GPIO callback thread. Only buffer here (a fast in-process
        # copy); do NOT flush. A flush forces a write() syscall that can stall
        # for tens of ms on SD-card writeback, during which further edges would
        # coalesce and pulses get lost. The buffer is flushed from poll() in the
        # main thread instead.
        if self._logfile is None:
            return
        pause_ms = pause * 1000 if pause is not None else -1
        self._logfile.write(
            '"%s";%f;%d;%d;%s;%.1f;%.1f\n'
            % (
                datetime.datetime.now().strftime("%d.%m.%y %H:%M:%S.%f"),
                time.time(),
                pulses,
                1 if was_enabled else 0,
                status,
                width * 1000,
                pause_ms,
            )
        )

    def poll(self):
        with self._lock:
            lp = self._last_pulse
            p = self._pulses
            ret = None
            if lp and lp + 0.5 < time.time():
                # Use the snapshot p, not self._pulses: a pulse landing between
                # the reads above and here would otherwise be evaluated against
                # the wrong (live) count and then wiped out by the reset below.
                if p in self._value_for_pulses:
                    ret = self._value_for_pulses[p]
                else:
                    ret = 0
                self._pulses = 0
                self._last_pulse = 0
        # Flush the pulse log here (main thread, outside the lock) rather than
        # in the ISR, so the callback thread never blocks on I/O and can't
        # miss edges.
        if ret is not None and self._logfile is not None:
            self._logfile.flush()
        return ret, p

    def inhibit(self):
        with self._lock:
            if self._inhibit_timer is not None:
                self._inhibit_timer.cancel()
                self._inhibit_timer = None
            self._inhibit_scheduled = False
            self._epoch += 1
            self._enabled = False
            self._pending_falling = None
        self._writeInhibitPin(1)

    def enable(self):
        with self._lock:
            if self._inhibit_timer is not None:
                self._inhibit_timer.cancel()
                self._inhibit_timer = None
            self._inhibit_scheduled = False
            self._epoch += 1
            if not self._enabled:
                self._pulses = 0
                self._last_pulse = 0
            self._enabled = True
            self._pending_falling = None
        self._writeInhibitPin(0)

    def isEnabled(self):
        return self._enabled

    def __init__(
        self,
        pulse_pin,
        inhibit_pin,
        value_for_pulses,
        log_path=None,
        inhibit_delay=0.1,
        min_pulse_width=0.02,
        max_pulse_width=0.15,
        min_pause=0.09,
    ):
        self._pulse_pin = pulse_pin
        self._inhibit_pin = inhibit_pin
        self._value_for_pulses = value_for_pulses
        self._inhibit_delay = inhibit_delay
        self._min_pulse_width = min_pulse_width
        self._max_pulse_width = max_pulse_width
        self._min_pause = min_pause
        self._lock = threading.Lock()
        self._epoch = 0
        self._inhibit_timer = None
        self._inhibit_scheduled = False
        self._pending_falling = None
        self._last_valid_rising = 0
        if log_path:
            is_new = not os.path.exists(log_path)
            self._logfile = open(log_path, "a")
            if is_new:
                self._logfile.write(
                    '"DT";"UT";"Pulses";"WasEnabled";"Status";"WidthMs";"PauseMs"\n'
                )
                self._logfile.flush()
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pulse_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self._inhibit_pin, GPIO.OUT)
        self.inhibit()
        GPIO.add_event_detect(
            self._pulse_pin, GPIO.BOTH, callback=self._edgeCallback, bouncetime=5
        )


if __name__ == "__main__":
    coin = CoinPulse(17, 22, {2: 0.5, 3: 1, 4: 2})
    # 	coin = CoinPulse(24, 22, {1:0.5, 2:1, 3:2})
    stored = 0
    input("Inhibited... Press Enter ")
    coin.enable()
    while True:
        m, p = coin.poll()
        if m:
            if m < 0:
                print("Coin not recognized, stored anyways")
            else:
                stored += m
                print("Received %1.2f Euro, now stored %1.2f Euro" % (m, stored))
            coin.enable()
