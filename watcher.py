"""Watcher: runs the camera in a background thread and tracks attention.
Based on my original WakeOrFace.py script (Haar cascades for face and eyes)."""
import os
import threading
import time
from datetime import timedelta
import cv2
import pygame

BASE = os.path.dirname(os.path.abspath(__file__))


class Watcher:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.frame = None
        self.thread = None
        self.s = {"break_every": 25}
        self.reset()

    def reset(self):
        self.error = None
        self.frame = None
        self.focus = 0.0          # seconds looking at the screen
        self.away = 0.0           # seconds away (total)
        self.away_now = 0.0       # current continuous away streak
        self.distractions = 0
        self.breaks = 0
        self.attentive = True
        self.on_break = False
        self.break_left = 0.0
        self.since_break = 0.0    # study seconds since last break

    def start(self, s):
        """s = settings dict: away1, away2, check_eyes, break_every, break_len (minutes)"""
        if self.running:
            return
        self.s = s
        self.reset()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)

    def status(self):
        with self.lock:
            return {
                "running": self.running, "error": self.error, "attentive": self.attentive,
                "focus": int(self.focus), "away": int(self.away),
                "away_now": int(self.away_now), "distractions": self.distractions,
                "breaks": self.breaks, "on_break": self.on_break,
                "break_left": int(self.break_left),
                "until_break": max(0, int(self.s["break_every"] * 60 - self.since_break)),
            }

    def _load_sound(self, name):
        try:
            return pygame.mixer.Sound(os.path.join(BASE, "sounds", name))
        except Exception:
            return None  # missing file: skip the sound instead of crashing

    def _loop(self):
        try:
            self._run()
        except Exception as e:
            self.error = f"Camera thread crashed: {e}"
        finally:
            self.running = False

    def _run(self):
        s1 = s2 = None
        try:
            pygame.mixer.init()
            s1 = self._load_sound("voice1.mp3")
            s2 = self._load_sound("voice2.mp3")
        except Exception:
            pass  # no audio device: keep running without sound
        face_det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        eye_det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

        # try several camera backends (Windows cameras are picky)
        cap = None
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if os.name == "nt" else [cv2.CAP_ANY]
        for b in backends:
            c = cv2.VideoCapture(0, b)
            if c.isOpened():
                cap = c
                break
            c.release()
        if cap is None:
            self.error = ("Could not open the camera. Close other apps using it (Zoom, Teams, "
                          "Camera app) and allow camera access in your OS privacy settings.")
            return
        played1 = played2 = False
        last = time.time()

        while self.running:
            ok, frame = cap.read()
            if not ok:
                self.error = "The camera stopped sending frames."
                break
            now = time.time()
            dt, last = now - last, now
            s = self.s

            attentive = False
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_det.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
                eyes = eye_det.detectMultiScale(gray[y:y + h // 2, x:x + w], 1.1, 8, minSize=(20, 20))
                for (ex, ey, ew, eh) in eyes:
                    cv2.rectangle(frame, (x + ex, y + ey), (x + ex + ew, y + ey + eh), (255, 0, 0), 2)
                if not s["check_eyes"] or len(eyes) >= 1:
                    attentive = True

            with self.lock:
                if self.on_break:
                    # camera is ignored during a break
                    self.break_left -= dt
                    attentive = True
                    if self.break_left <= 0:
                        self.on_break = False
                        self.since_break = 0.0
                    label, color = f"Break {int(self.break_left)}s", (255, 200, 0)
                else:
                    self.attentive = attentive
                    self.since_break += dt
                    if attentive:
                        self.focus += dt
                        self.away_now = 0.0
                        played1 = played2 = False
                        if s1: s1.stop()
                        if s2: s2.stop()
                        label, color = "Focused", (0, 255, 0)
                    else:
                        self.away += dt
                        self.away_now += dt
                        label, color = f"Away {int(self.away_now)}s", (0, 0, 255)
                        if self.away_now >= s["away1"] and not played1:
                            played1 = True
                            self.distractions += 1
                            if s1: s1.play()
                        if self.away_now >= s["away2"] and not played2:
                            played2 = True
                            if s2: s2.play()
                    if self.since_break >= s["break_every"] * 60:
                        self.on_break = True
                        self.break_left = s["break_len"] * 60
                        self.breaks += 1
                        if s1: s1.stop()
                        if s2: s2.stop()

            cv2.putText(frame, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
            self.frame = frame

        cap.release()
        self.running = False
