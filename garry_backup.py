import sys
import random
import math
import time
import threading
import subprocess
import json
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtGui import QPixmap, QCursor, QTransform
from PyQt6.QtCore import Qt, QTimer

app = QApplication(sys.argv)
pixmap = QPixmap("/usr/share/garry/lizard.png")
screens = app.screens()
primary_geo = app.primaryScreen().geometry()

instances = []
pending_commands = []
lock = threading.Lock()


def get_combined_desktop_limits():
    all_screens = app.screens()
    min_x = min(s.geometry().x() for s in all_screens)
    min_y = min(s.geometry().y() for s in all_screens)
    max_x = max(s.geometry().x() + s.geometry().width() for s in all_screens)
    max_y = max(s.geometry().y() + s.geometry().height() for s in all_screens)
    return float(min_x), float(min_y), float(max_x), float(max_y)


class GarryPet:
    def __init__(self):
        self.window = QLabel()
        self.window.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.window.setMouseTracking(True)
        self.window.setPixmap(pixmap)
        self.window.resize(pixmap.size())

        self.x = float(random.randint(primary_geo.x(), primary_geo.x() + primary_geo.width() - pixmap.width()))
        self.y = float(random.randint(primary_geo.y(), primary_geo.y() + primary_geo.height() - pixmap.height()))
        self.dx = 0.0
        self.dy = 0.0

        self.flipping = False
        self.flip_angle = 0
        self.normal_panic = False
        self.normal_panic_end = 0
        self.extreme_panic = False
        self.extreme_panic_end = 0
        self.is_sleeping = False
        self.tp_requested = False

        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.current_ws = 1

        self.window.mousePressEvent = self.mousePressEvent
        self.window.mouseMoveEvent = self.mouseMoveEvent
        self.window.mouseReleaseEvent = self.mouseReleaseEvent
        self.window.show()

    def switch_workspace(self, n):
        self.current_ws = n
        lua_cmd = f'hl.dispatch(hl.dsp.window.move({{ workspace = "{n}", follow = false, window = "pid:{subprocess.os.getpid()}" }}))'
        subprocess.run(["hyprctl", "eval", lua_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def apply_move(self):
        self.window.move(int(self.x), int(self.y))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_sleeping:
                self.normal_panic = True
                self.normal_panic_end = time.time() + 1.0

        if event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.dragging = True
                self.drag_offset_x = event.position().x()
                self.drag_offset_y = event.position().y()

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return

        self.x = event.globalPosition().x() - self.drag_offset_x
        self.y = event.globalPosition().y() - self.drag_offset_y

        min_x, min_y, max_x, max_y = get_combined_desktop_limits()
        self.x = max(min_x, min(self.x, max_x - float(pixmap.width())))
        self.y = max(min_y, min(self.y, max_y - float(pixmap.height())))
        self.apply_move()

        edge = 30
        current_screen_geo = primary_geo
        for s in app.screens():
            if s.geometry().contains(int(self.x), int(self.y)):
                current_screen_geo = s.geometry()
                break

        local_max_x = float(current_screen_geo.x() + current_screen_geo.width() - pixmap.width())

        if self.x <= float(current_screen_geo.x() + edge):
            self.switch_workspace(max(1, self.current_ws - 1))
            self.x = local_max_x - 50.0
        elif self.x >= local_max_x - float(edge):
            self.switch_workspace(self.current_ws + 1)
            self.x = float(current_screen_geo.x() + 50)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def process_tick(self):
        if self.dragging:
            return

        min_x, min_y, max_x, max_y = get_combined_desktop_limits()

        if self.tp_requested:
            self.is_sleeping = False
            self.tp_requested = False
            try:
                ws_res = subprocess.run(["hyprctl", "activeworkspace", "-j"], capture_output=True, text=True)
                active_ws = json.loads(ws_res.stdout)
                target_ws_id = active_ws.get("id", 1)

                mon_res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True)
                monitors = json.loads(mon_res.stdout)

                target_geo = None
                for mon in monitors:
                    if mon.get("focused", False):
                        target_geo = (float(mon["x"]), float(mon["y"]), float(mon["width"]), float(mon["height"]))
                        break

                if not target_geo:
                    target_geo = (float(primary_geo.x()), float(primary_geo.y()), float(primary_geo.width()), float(primary_geo.height()))

                mon_x, mon_y, mon_w, mon_h = target_geo
                target_x = mon_x + (mon_w / 2.0) - (float(pixmap.width()) / 2.0)
                target_y = mon_y + (mon_h / 2.0) - (float(pixmap.height()) / 2.0)

                self.x = max(mon_x, min(target_x, mon_x + mon_w - float(pixmap.width())))
                self.y = max(mon_y, min(target_y, mon_y + mon_h - float(pixmap.height())))

                self.switch_workspace(target_ws_id)
                self.apply_move()
            except:
                pass
            return

        if self.is_sleeping:
            self.x += random.uniform(-0.4, 0.4)
            self.y += random.uniform(-0.4, 0.4)
            self.x = max(min_x, min(self.x, max_x - float(pixmap.width())))
            self.y = max(min_y, min(self.y, max_y - float(pixmap.height())))
            self.apply_move()
            return

        now = time.time()

        if self.extreme_panic:
            if now > self.extreme_panic_end:
                self.extreme_panic = False
            else:
                self.x += random.uniform(-600, 600)
                self.y += random.uniform(-600, 600)
                if random.random() < 0.08:
                    self.switch_workspace(random.randint(1, 9))
                self.x = max(min_x, min(self.x, max_x - float(pixmap.width())))
                self.y = max(min_y, min(self.y, max_y - float(pixmap.height())))
                self.apply_move()
                return

        if self.normal_panic:
            if now > self.normal_panic_end:
                self.normal_panic = False
            else:
                mx = self.x - QCursor.pos().x()
                my = self.y - QCursor.pos().y()
                dist = math.hypot(mx, my)
                if dist > 0:
                    self.x += (mx / dist) * 12
                    self.y += (my / dist) * 12
                if random.random() < 0.03:
                    self.switch_workspace(random.randint(1, 9))
                self.x = max(min_x, min(self.x, max_x - float(pixmap.width())))
                self.y = max(min_y, min(self.y, max_y - float(pixmap.height())))
                self.apply_move()
                return

        if self.flipping:
            self.flip_angle += 80
            transform = QTransform()
            transform.rotate(self.flip_angle)
            self.window.setPixmap(pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation))
            if self.flip_angle >= 360:
                self.flipping = False
                self.window.setPixmap(pixmap)
            self.apply_move()
            return

        self.dx += random.uniform(-0.5, 0.5)
        self.dy += random.uniform(-0.5, 0.5)

        speed = math.hypot(self.dx, self.dy)
        max_speed = 2.5
        if speed > max_speed:
            self.dx = (self.dx / speed) * max_speed
            self.dy = (self.dy / speed) * max_speed

        self.x += self.dx
        self.y += self.dy

        if self.x < min_x:
            self.x = max_x - float(pixmap.width())
        elif self.x > max_x - float(pixmap.width()):
            self.x = min_x

        if self.y < min_y:
            self.y = max_y - float(pixmap.height())
        elif self.y > max_y - float(pixmap.height()):
            self.y = min_y

        if random.random() < 0.002:
            self.switch_workspace(random.randint(1, 9))

        self.apply_move()


instances.append(GarryPet())


def command_loop():
    global pending_commands

    while True:
        try:
            line = input("Garry > ").strip()
            if not line:
                continue

            parts = line.split()
            target_idx = None

            if len(parts) > 1:
                try:
                    target_idx = int(parts[-1])
                    cmd_string = " ".join(parts[:-1]).lower()
                except ValueError:
                    cmd_string = line.lower()
            else:
                cmd_string = line.lower()

            with lock:
                pending_commands.append((cmd_string, target_idx))

        except (EOFError, KeyboardInterrupt):
            break


threading.Thread(target=command_loop, daemon=True).start()


def main_tick():
    global pending_commands, instances
    with lock:
        cmds = list(pending_commands)
        pending_commands.clear()

    for cmd_string, idx in cmds:
        if cmd_string == "crash":
            for _ in range(200):
                instances.append(GarryPet())
            for target in instances:
                target.extreme_panic = True
                target.extreme_panic_end = time.time() + 10.0
            continue

        targets = []
        if idx is not None:
            if 1 <= idx <= len(instances):
                targets.append(instances[idx - 1])
        else:
            targets = list(instances)

        if cmd_string == "clone":
            instances.append(GarryPet())
            continue

        for target in targets:
            if cmd_string == "tp":
                target.tp_requested = True
            elif cmd_string == "sleep":
                target.is_sleeping = True
            elif cmd_string == "wake":
                target.is_sleeping = False
            elif cmd_string == "flip":
                target.flipping = True
                target.flip_angle = 0
            elif cmd_string == "panic":
                target.extreme_panic = True
                target.extreme_panic_end = time.time() + 10.0
            elif cmd_string.startswith("ws "):
                try:
                    target.switch_workspace(int(cmd_string.split()[1]))
                except:
                    pass
            elif cmd_string.startswith("desk "):
                try:
                    target.switch_workspace(int(cmd_string.split()[1]))
                except:
                    pass

    for inst in instances:
        inst.process_tick()


timer = QTimer()
timer.timeout.connect(main_tick)
timer.start(16)

try:
    sys.exit(app.exec())
except KeyboardInterrupt:
    sys.exit(0)
