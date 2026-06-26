sudo tee /usr/share/garry/garry.py << 'EOF'
import sys, random, math, time, threading, subprocess, json, os
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtGui import QPixmap, QCursor, QTransform
from PyQt6.QtCore import Qt, QTimer

NOTIFY_INTERVAL = 3600000
FACTS_FILE = "/usr/share/garry/facts.txt"
JOKES_FILE = "./jokes.txt"

app = QApplication(sys.argv)
pixmap = QPixmap("/usr/share/garry/lizard.png")
geo = app.primaryScreen().geometry()
instances, pending_cmds, lock = [], [], threading.Lock()

def get_limits():
    screens = app.screens()
    return (float(min(s.geometry().x() for s in screens)), float(min(s.geometry().y() for s in screens)),
            float(max(s.geometry().x() + s.geometry().width() for s in screens)), float(max(s.geometry().y() + s.geometry().height() for s in screens)))

class GarryPet:
    def __init__(self):
        self.window = QLabel()
        self.window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.window.setMouseTracking(True)
        self.window.setPixmap(pixmap)
        self.window.resize(pixmap.size())
        self.x = float(random.randint(geo.x(), geo.x() + geo.width() - pixmap.width()))
        self.y = float(random.randint(geo.y(), geo.y() + geo.height() - pixmap.height()))
        self.dx, self.dy, self.flip_angle, self.current_ws = 0.0, 0.0, 0, 1
        self.flipping = self.normal_panic = self.extreme_panic = self.is_sleeping = self.tp_requested = self.dragging = False
        self.drag_offset_x = self.drag_offset_y = self.normal_panic_end = self.extreme_panic_end = 0
        self.window.mousePressEvent = self.press
        self.window.mouseMoveEvent = self.move
        self.window.mouseReleaseEvent = self.release
        self.window.show()

    def switch_workspace(self, n):
        self.current_ws = n
        cmd = f'hl.dispatch(hl.dsp.window.move({{ workspace = "{n}", follow = false, window = "pid:{subprocess.os.getpid()}" }}))'
        subprocess.run(["hyprctl", "eval", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def apply(self): self.window.move(int(self.x), int(self.y))
    def release(self, e): self.dragging = False

    def press(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if not self.is_sleeping: self.normal_panic, self.normal_panic_end = True, time.time() + 1.0
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.dragging, self.drag_offset_x, self.drag_offset_y = True, e.position().x(), e.position().y()

    def move(self, e):
        if not self.dragging: return
        self.x, self.y = e.globalPosition().x() - self.drag_offset_x, e.globalPosition().y() - self.drag_offset_y
        min_x, min_y, max_x, max_y = get_limits()
        self.x, self.y = max(min_x, min(self.x, max_x - pixmap.width())), max(min_y, min(self.y, max_y - pixmap.height()))
        self.apply()
        s_geo = geo
        for s in app.screens():
            if s.geometry().contains(int(self.x), int(self.y)): s_geo = s.geometry(); break
        lx = float(s_geo.x() + s_geo.width() - pixmap.width())
        if self.x <= float(s_geo.x() + 30): self.switch_workspace(max(1, self.current_ws - 1)); self.x = lx - 50.0
        elif self.x >= lx - 30.0: self.switch_workspace(self.current_ws + 1); self.x = float(s_geo.x() + 50)

    def process_tick(self):
        if self.dragging: return
        min_x, min_y, max_x, max_y = get_limits()
        if self.tp_requested:
            self.is_sleeping = self.tp_requested = False
            try:
                ws = json.loads(subprocess.run(["hyprctl", "activeworkspace", "-j"], capture_output=True, text=True).stdout)
                mons = json.loads(subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True).stdout)
                tg = next(((float(m["x"]), float(m["y"]), float(m["width"]), float(m["height"])) for m in mons if m.get("focused", False)), (float(geo.x()), float(geo.y()), float(geo.width()), float(geo.height())))
                mx, my, mw, mh = tg
                self.x, self.y = max(mx, min(mx + (mw / 2.0) - (pixmap.width() / 2.0), mx + mw - pixmap.width())), max(my, min(my + (mh / 2.0) - (pixmap.height() / 2.0), my + mh - pixmap.height()))
                self.switch_workspace(ws.get("id", 1)); self.apply()
            except Exception: pass
            return
        if self.is_sleeping:
            self.x, self.y = max(min_x, min(self.x + random.uniform(-0.4, 0.4), max_x - pixmap.width())), max(min_y, min(self.y + random.uniform(-0.4, 0.4), max_y - pixmap.height()))
            self.apply(); return
        now = time.time()
        if self.extreme_panic:
            if now > self.extreme_panic_end: self.extreme_panic = False
            else:
                self.x, self.y = max(min_x, min(self.x + random.uniform(-600, 600), max_x - pixmap.width())), max(min_y, min(self.y + random.uniform(-600, 600), max_y - pixmap.height()))
                if random.random() < 0.08: self.switch_workspace(random.randint(1, 9))
                self.apply(); return
        if self.normal_panic:
            if now > self.normal_panic_end: self.normal_panic = False
            else:
                mx, my = self.x - QCursor.pos().x(), self.y - QCursor.pos().y()
                dist = math.hypot(mx, my)
                if dist > 0: self.x, self.y = max(min_x, min(self.x + (mx / dist) * 12, max_x - pixmap.width())), max(min_y, min(self.y + (my / dist) * 12, max_y - pixmap.height()))
                if random.random() < 0.03: self.switch_workspace(random.randint(1, 9))
                self.apply(); return
        if self.flipping:
            self.flip_angle += 80
            t = QTransform()
            t.rotate(self.flip_angle)
            self.window.setPixmap(pixmap.transformed(t, Qt.TransformationMode.SmoothTransformation))
            if self.flip_angle >= 360: self.flipping = False; self.window.setPixmap(pixmap)
            self.apply(); return
        self.dx, self.dy = self.dx + random.uniform(-0.5, 0.5), self.dy + random.uniform(-0.5, 0.5)
        spd = math.hypot(self.dx, self.dy)
        if spd > 2.5: self.dx, self.dy = (self.dx / spd) * 2.5, (self.dy / spd) * 2.5
        self.x, self.y = self.x + self.dx, self.y + self.dy
        if self.x < min_x: self.x = max_x - pixmap.width()
        elif self.x > max_x - pixmap.width(): self.x = min_x
        if self.y < min_y: self.y = max_y - pixmap.height()
        elif self.y > max_y - pixmap.height(): self.y = min_y
        if random.random() < 0.002: self.switch_workspace(random.randint(1, 9))
        self.apply()

instances.append(GarryPet())

def cmd_loop():
    while True:
        try:
            line = input("Garry > ").strip()
            if not line: continue
            parts = line.split()
            idx = None
            if len(parts) > 1:
                try: idx = int(parts[-1]); cmd_str = " ".join(parts[:-1]).lower()
                except ValueError: cmd_str = line.lower()
            else: cmd_str = line.lower()
            with lock: pending_cmds.append((cmd_str, idx))
        except (EOFError, KeyboardInterrupt): break

threading.Thread(target=cmd_loop, daemon=True).start()

def main_tick():
    global instances
    with lock:
        cmds = list(pending_cmds)
        pending_cmds.clear()
    for cmd_str, idx in cmds:
        if cmd_str == "crash":
            for _ in range(200): instances.append(GarryPet())
            for t in instances: t.extreme_panic, t.extreme_panic_end = True, time.time() + 10.0
            continue
        targets = [instances[idx - 1]] if idx is not None and 1 <= idx <= len(instances) else list(instances)
        if cmd_str == "clone": instances.append(GarryPet()); continue
        for t in targets:
            if cmd_str == "tp": t.tp_requested = True
            elif cmd_str == "sleep": t.is_sleeping = True
            elif cmd_str == "wake": t.is_sleeping = False
            elif cmd_str == "flip": t.flipping, t.flip_angle = True, 0
            elif cmd_str == "panic": t.extreme_panic, t.extreme_panic_end = True, time.time() + 10.0
            elif cmd_str.startswith("ws ") or cmd_str.startswith("desk "):
                try: t.switch_workspace(int(cmd_str.split()[1]))
                except Exception: pass
    for i in instances: i.process_tick()

def send_file_line(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            if lines: subprocess.run(["notify-send", "Garry:", random.choice(lines)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

timer = QTimer()
timer.timeout.connect(main_tick)
timer.start(16)

f_timer = QTimer()
f_timer.timeout.connect(lambda: send_file_line(FACTS_FILE))
f_timer.start(NOTIFY_INTERVAL)

j_timer = QTimer()
j_timer.timeout.connect(lambda: send_file_line(JOKES_FILE))
j_timer.start(NOTIFY_INTERVAL)

QTimer.singleShot(1000, lambda: send_file_line(FACTS_FILE))
QTimer.singleShot(5000, lambda: send_file_line(JOKES_FILE))

try: sys.exit(app.exec())
except KeyboardInterrupt: sys.exit(0)
EOF
