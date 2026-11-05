"""Chapter Player - prototip (PySide6 + libmpv)

Cerinte:
    pip install PySide6 python-mpv
    + mpv-2.dll (libmpv) pus in acelasi folder cu acest fisier.
"""
import os
import sys
import json
import locale
import hashlib
import tempfile
import threading

if getattr(sys, "frozen", False):
    # .exe PyInstaller (onedir sau onefile): fisierele incluse sunt in _MEIPASS
    BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
os.environ["PATH"] = BASE + os.pathsep + os.environ.get("PATH", "")
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(BASE)

from PySide6.QtCore import Qt, QTimer, QEvent, Signal
from PySide6.QtGui import QPainter, QColor, QKeySequence, QShortcut, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QListWidget, QListWidgetItem, QFileDialog, QComboBox,
    QSplitter, QStyle, QCheckBox, QMenu, QInputDialog,
)

import mpv

try:
    import numpy as np
except ImportError:  # forma de unda dezactivata fara numpy
    np = None

STATE_FILE = os.path.join(os.path.expanduser("~"), ".chapter_player.json")
COLOR_PLAYER = "#1fae5b"  # markerele puse din aplicatie (Audacity ramane alb)
SPEEDS = [f"{i / 10:.1f}" for i in range(5, 31)]  # 0.5 ... 3.0, din 0.1 in 0.1


def fmt(sec):
    sec = max(0, int(sec or 0))
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class ChapterSlider(QSlider):
    """Bara de progres pentru toata inregistrarea, cu marcaje la capitole."""

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.marks = []  # fractii 0..1
        self.setRange(0, 10000)
        self.setFixedHeight(32)

    def set_marks(self, marks):
        self.marks = marks
        self.update()

    def _value_at(self, x):
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), x, self.width())

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setValue(self._value_at(int(e.position().x())))
            self.sliderMoved.emit(self.value())
            self.setSliderDown(True)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.isSliderDown():
            self.setValue(self._value_at(int(e.position().x())))
            self.sliderMoved.emit(self.value())
        super().mouseMoveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        top, bh = h // 2 - 4, 8
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a3a3a"))
        p.drawRoundedRect(0, top, w, bh, 4, 4)
        frac = self.value() / max(1, self.maximum())
        p.setBrush(QColor("#3b9cff"))
        p.drawRoundedRect(0, top, int(w * frac), bh, 4, 4)
        for m, src in self.marks:
            p.setBrush(QColor(COLOR_PLAYER if src == "player" else "#ffffff"))
            x = int(m * w)
            p.drawRect(x - 1, top - 4, 2, bh + 8)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(int(w * frac) - 7, h // 2 - 7, 14, 14)


class WaveformView(QWidget):
    """Forma de unda a intregii inregistrari, cu marcaje de capitole si pozitia curenta."""

    seek_requested = Signal(float)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(90)
        self.peaks = None
        self.marks = []
        self.progress = 0.0
        self.message = "Nicio inregistrare"
        self._cols = None
        self._cols_w = 0

    def set_message(self, text):
        self.peaks = None
        self._cols = None
        self.message = text
        self.update()

    def set_peaks(self, peaks):
        self.peaks = peaks
        self._cols = None
        self.update()

    def set_marks(self, marks):
        self.marks = marks
        self.update()

    def set_progress(self, frac):
        if abs(frac - self.progress) > 0.0004:
            self.progress = frac
            self.update()

    def _columns(self, w):
        if self._cols is None or self._cols_w != w:
            n = len(self.peaks)
            idx = np.linspace(0, n, w + 1).astype(np.int64)
            starts = np.minimum(idx[:-1], n - 1)
            self._cols = np.maximum.reduceat(self.peaks, starts)
            self._cols_w = w
        return self._cols

    def _emit(self, e):
        w = max(1, self.width())
        self.seek_requested.emit(min(1.0, max(0.0, e.position().x() / w)))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._emit(e)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._emit(e)

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#1e1e1e"))
        mid = h // 2
        if self.peaks is None or len(self.peaks) == 0 or np is None:
            p.setPen(QColor("#888888"))
            p.drawText(self.rect(), Qt.AlignCenter, self.message)
            return
        cols = self._columns(w)
        px = int(self.progress * w)
        half = mid - 4
        played, rest = QColor("#3b9cff"), QColor("#5d6b7a")
        for x in range(w):
            amp = int(cols[x] * half)
            p.setPen(played if x <= px else rest)
            p.drawLine(x, mid - amp, x, mid + amp)
        for m, src in self.marks:
            p.setPen(QColor(COLOR_PLAYER if src == "player" else "#ffffff"))
            x = int(m * w)
            p.drawLine(x, 0, x, h)
        p.setPen(QColor("#ffcc00"))
        p.drawLine(px, 0, px, h)


class Player(QMainWindow):
    wave_ready = Signal(object, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chapter Player")
        _ico = os.path.join(BASE, "app_icon.ico")
        if os.path.exists(_ico):
            self.setWindowIcon(QIcon(_ico))
        self.resize(1100, 650)
        self.setAcceptDrops(True)
        self.state = self._load_state()
        self.path = None
        self.chapters = []
        self.duration = 0
        self.has_video = None
        self.key = None          # cheia normalizata a fisierului curent
        self.restore_pos = 0.0   # pozitia de reluat
        self.restored = True     # True dupa ce pozitia a fost aplicata
        self.ext_chapters = None  # capitole din fisier Audacity

        # --- zona video / copertă ---
        self.video = QWidget()
        self.video.setStyleSheet("background:black;")
        self.video.setAttribute(Qt.WA_NativeWindow)

        # --- lista de capitole ---
        self.list = QListWidget()
        self.list.setMinimumWidth(320)
        self.list.itemClicked.connect(self.on_chapter_click)
        self.list.setStyleSheet(
            "QListWidget{font-size:14px;} QListWidget::item{padding:6px;}"
        )

        split = QSplitter()
        split.addWidget(self.video)
        split.addWidget(self.list)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)

        # --- forma de unda ---
        self.wave = WaveformView()
        self.wave.seek_requested.connect(self.on_seek_fraction)
        self.wave_ready.connect(self.on_wave_ready)

        # --- controale ---
        self.slider = ChapterSlider()
        self.slider.sliderMoved.connect(self.on_seek)
        self.lbl_time = QLabel("0:00 / 0:00")
        self.lbl_chapter = QLabel("")
        self.lbl_chapter.setStyleSheet("font-weight:bold;")

        def btn(text, fn):
            b = QPushButton(text)
            b.clicked.connect(fn)
            return b

        self.btn_play = btn("▶", self.toggle)
        controls = QHBoxLayout()
        controls.addWidget(btn("⏮ Cap.", self.prev_chapter))
        controls.addWidget(btn("−10s", lambda: self.skip(-10)))
        controls.addWidget(self.btn_play)
        controls.addWidget(btn("+10s", lambda: self.skip(10)))
        controls.addWidget(btn("Cap. ⏭", self.next_chapter))
        self.speed = QComboBox()
        self.speed.addItems([s + "x" for s in SPEEDS])
        self.speed.setCurrentIndex(SPEEDS.index("1.0"))
        self.speed.currentIndexChanged.connect(self.on_speed)
        controls.addWidget(btn("−", lambda: self.change_speed(-1)))
        controls.addWidget(self.speed)
        controls.addWidget(btn("+", lambda: self.change_speed(1)))
        self.resume = QCheckBox("Reia poziția")
        self.resume.setChecked(bool(self.state.get("__resume__", False)))
        self.resume.toggled.connect(self.on_resume_toggled)
        controls.addWidget(self.resume)
        controls.addStretch()
        controls.addWidget(self.lbl_chapter)
        controls.addStretch()
        controls.addWidget(self.lbl_time)

        top = QHBoxLayout()
        top.addWidget(btn("Selectare înregistrare", self.open_dialog))
        top.addWidget(btn("Selectare markere", self.open_labels_dialog))
        top.addStretch()

        root = QVBoxLayout()
        root.addLayout(top)
        root.addWidget(split, 1)
        root.addWidget(self.wave)
        root.addWidget(self.slider)
        root.addLayout(controls)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        # --- mpv ---
        self.mpv = mpv.MPV(
            wid=str(int(self.video.winId())),
            input_default_bindings=False,
            input_vo_keyboard=False,
            osc=False,
            keep_open="yes",
        )

        # scurtaturi: Ctrl+O prin QShortcut, restul prin event filter (vezi eventFilter)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_dialog)
        QApplication.instance().installEventFilter(self)

        # nicio componenta nu "fura" tastele (sageti, space)
        for w in [self.list, self.slider, self.speed, self.resume] + self.findChildren(QPushButton):
            w.setFocusPolicy(Qt.NoFocus)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(250)
        self._save_counter = 0

        if len(sys.argv) > 1:
            self.load(sys.argv[1])

    # ---------- forma de unda ----------
    def on_seek_fraction(self, f):
        if self.duration:
            self.mpv.seek(f * self.duration, "absolute")

    def on_wave_ready(self, peaks, path):
        if path != self.path:
            return
        if peaks is None:
            self.wave.set_message("Forma de unda indisponibila")
        else:
            self.wave.set_peaks(peaks)

    def _wave_worker(self, path):
        peaks = None
        try:
            peaks = self._compute_peaks(path)
        except Exception:
            peaks = None
        self.wave_ready.emit(peaks, path)

    @staticmethod
    def _compute_peaks(path):
        if np is None:
            return None
        cache_dir = os.path.join(os.path.expanduser("~"), ".chapter_player_cache")
        st = os.stat(path)
        key = hashlib.sha1(f"{path}|{st.st_size}|{st.st_mtime}".encode()).hexdigest()[:16]
        cache = os.path.join(cache_dir, key + ".npy")
        if os.path.exists(cache):
            try:
                return np.load(cache)
            except Exception:
                pass

        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            # al doilea mpv, doar pentru decodare rapida (mono, 8 kHz) intr-un WAV temporar
            m = mpv.MPV(
                vid="no", vo="null", ao="pcm", ao_pcm_file=tmp,
                audio_samplerate=8000, audio_channels="mono", audio_format="s16",
                input_default_bindings=False, osc=False,
            )
            try:
                m.play(path)
                m.wait_for_playback()
            finally:
                m.terminate()

            raw = open(tmp, "rb").read()
            if raw[:4] == b"RIFF":
                raw = raw[44:]
            raw = raw[: len(raw) // 2 * 2]
            a = np.frombuffer(raw, dtype=np.int16).astype(np.int32)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

        bucket = 80  # 10 ms
        n = len(a) // bucket
        if n < 2:
            return None
        arr = np.abs(a[: n * bucket]).reshape(n, bucket).max(axis=1).astype(np.float32)
        ref = float(np.percentile(arr, 99.5)) or float(arr.max()) or 1.0
        arr = np.clip(arr / ref, 0, 1) ** 0.6  # scala care scoate in evidenta sunetele slabe
        try:
            os.makedirs(cache_dir, exist_ok=True)
            np.save(cache, arr)
        except Exception:
            pass
        return arr

    # ---------- taste ----------
    def on_resume_toggled(self, on):
        self.state["__resume__"] = bool(on)
        self._save_state()

    def change_speed(self, step):
        i = max(0, min(self.speed.count() - 1, self.speed.currentIndex() + step))
        self.speed.setCurrentIndex(i)  # declanseaza on_speed

    def eventFilter(self, obj, e):
        if e.type() == QEvent.KeyPress and self.isActiveWindow():
            if QApplication.activePopupWidget() is not None:
                return False
            if e.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
                return False
            key, text, rep_ = e.key(), e.text(), e.isAutoRepeat()
            if key == Qt.Key_Space:
                if not rep_:
                    self.toggle()
                return True
            if key == Qt.Key_Left:
                self.skip(-10)
                return True
            if key == Qt.Key_Right:
                self.skip(10)
                return True
            if key in (Qt.Key_Up, Qt.Key_PageDown) and not rep_:
                self.next_chapter()
                return True
            if key in (Qt.Key_Down, Qt.Key_PageUp) and not rep_:
                self.prev_chapter()
                return True
            if text in ("<", ",") and not rep_:
                self.change_speed(-1)
                return True
            if text in (">", ".") and not rep_:
                self.change_speed(1)
                return True
        return super().eventFilter(obj, e)

    # ---------- stare ----------
    def _load_state(self):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _key(path):
        return os.path.normcase(os.path.abspath(path))

    def _save_state(self):
        if self.key and self.restored:
            try:
                pos = self.mpv.time_pos
                dur = self.mpv.duration
            except Exception:
                pos, dur = None, None
            if pos is not None:
                if dur and pos >= dur - 3:
                    self.state.pop(self.key, None)  # ascultat pana la capat
                else:
                    self.state[self.key] = round(float(pos), 2)
        try:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f)
            os.replace(tmp, STATE_FILE)
        except Exception:
            pass

    # ---------- incarcare ----------
    def open_dialog(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Selectare înregistrare", "",
            "Media (*.m4a *.m4b *.mp3 *.mp4 *.mkv *.flac *.ogg *.opus *.wav *.aac *.wma);;Toate (*.*)",
        )
        if p:
            self.load(p)

    def load(self, path):
        self._save_state()  # salveaza pozitia fisierului anterior
        self.path = path
        self.key = self._key(path)
        self.chapters = []
        self.list.clear()
        self.ext_chapters = self.find_labels(path)
        pos = float(self.state.get(self.key, 0) or 0) if self.resume.isChecked() else 0.0
        self.restore_pos = pos if pos > 1 else 0.0
        self.restored = self.restore_pos == 0.0  # pana la aplicare nu salvam nimic
        self.mpv.pause = True
        self.mpv.loadfile(path)
        self.mpv.pause = True
        self.wave.set_message("Se calculeaza forma de unda...")
        threading.Thread(target=self._wave_worker, args=(path,), daemon=True).start()
        self.setWindowTitle(f"Chapter Player - {os.path.basename(path)}")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        media = [f for f in files if not f.lower().endswith(".txt")]
        labels = [f for f in files if f.lower().endswith(".txt")]
        if media:
            self.load(media[0])
        if labels and self.path:
            self.load_labels(labels[0])

    # ---------- markere Audacity ----------
    @staticmethod
    def parse_labels(path):
        """Citeste un fisier Audacity 'Export Labels': start<TAB>end<TAB>text."""
        out = []
        for enc in ("utf-8-sig", "utf-16", "cp1250", "latin-1"):
            try:
                with open(path, encoding=enc) as f:
                    lines = f.read().splitlines()
                break
            except Exception:
                lines = None
        if lines is None:
            return []
        for line in lines:
            if not line.strip() or line.startswith("\\"):
                continue  # linii goale / frecvente (spectral)
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            try:
                t = float(parts[0].strip().replace(",", "."))
            except ValueError:
                continue
            title = parts[2].strip() if len(parts) >= 3 else ""
            out.append({"time": t, "title": title})
        out.sort(key=lambda c: c["time"])
        return out

    def find_labels(self, media_path):
        base = os.path.splitext(media_path)[0]
        for cand in (base + ".txt", base + "_labels.txt", base + ".labels.txt",
                     base + " labels.txt", base + "-labels.txt"):
            if os.path.exists(cand):
                chs = self.parse_labels(cand)
                if chs:
                    return chs
        return None

    def load_labels(self, path):
        chs = self.parse_labels(path)
        if chs:
            self.ext_chapters = chs

    def open_labels_dialog(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Selectare markere (Audacity, Export Labels)", os.path.dirname(self.path or ""),
            "Text (*.txt);;Toate (*.*)",
        )
        if p and self.path:
            self.load_labels(p)

    def chapters_now(self):
        base = self.ext_chapters if self.ext_chapters is not None else (self.mpv.chapter_list or [])
        src = "audacity" if self.ext_chapters is not None else "file"
        chs = [{"time": c.get("time", 0), "title": c.get("title", ""), "src": src} for c in base]
        chs.sort(key=lambda c: c["time"])
        # daca primul marker nu e la 0, adaugam un capitol "Inceput" de la 0
        if chs and chs[0]["time"] > 0.5:
            chs.insert(0, {"time": 0.0, "title": "Început", "src": "auto"})
        return chs

    @staticmethod
    def current_index(pos, chs):
        idx = None
        for i, c in enumerate(chs):
            if c["time"] <= pos + 0.05:
                idx = i
            else:
                break
        return idx

    # ---------- capitole ----------
    def rebuild_chapters(self, chapters):
        self.chapters = chapters
        self.list.clear()
        for i, c in enumerate(chapters):
            start = c.get("time", 0)
            end = chapters[i + 1]["time"] if i + 1 < len(chapters) else self.duration
            title = c.get("title") or f"Capitol {i + 1}"
            it = QListWidgetItem(f"{i + 1:>2}. {title}\n      {fmt(start)}  •  {fmt(end - start)}")
            self.list.addItem(it)
        self._update_marks()

    def _update_marks(self):
        marks = ([(c["time"] / self.duration, c.get("src")) for c in self.chapters if c["time"] > 0.5]
                 if self.duration > 0 else [])
        self.slider.set_marks(marks)
        self.wave.set_marks(marks)

    def on_chapter_click(self, item):
        i = self.list.row(item)
        if 0 <= i < len(self.chapters):
            self.mpv.seek(self.chapters[i]["time"], "absolute")

    def prev_chapter(self):
        chs = self.chapters
        if not chs:
            return
        pos = self.mpv.time_pos or 0
        cur = self.current_index(pos, chs)
        if cur is None:
            return
        # daca suntem la >3s in capitol, mergem la inceputul lui
        if pos - chs[cur]["time"] > 3 or cur == 0:
            self.mpv.seek(chs[cur]["time"], "absolute")
        else:
            self.mpv.seek(chs[cur - 1]["time"], "absolute")

    def next_chapter(self):
        chs = self.chapters
        if not chs:
            return
        cur = self.current_index(self.mpv.time_pos or 0, chs)
        nxt = 0 if cur is None else cur + 1
        if nxt < len(chs):
            self.mpv.seek(chs[nxt]["time"], "absolute")

    # ---------- redare ----------
    def toggle(self):
        self.mpv.pause = not self.mpv.pause
        self._save_state()

    def skip(self, s):
        try:
            self.mpv.seek(s, "relative")
        except Exception:
            pass

    def on_seek(self, v):
        if self.duration:
            self.mpv.seek(v / self.slider.maximum() * self.duration, "absolute")

    def on_speed(self, i):
        self.mpv.speed = float(SPEEDS[i])

    # ---------- actualizare UI ----------
    def tick(self):
        try:
            dur = self.mpv.duration or 0
            pos = self.mpv.time_pos or 0
            chs = self.chapters_now()
            cur = self.current_index(pos, chs)
            paused = self.mpv.pause
        except Exception:
            return

        try:
            tracks = self.mpv.track_list or []
        except Exception:
            tracks = []
        has_video = any(
            t.get("type") == "video" and not t.get("albumart") for t in tracks
        )
        if has_video != self.has_video:
            self.has_video = has_video
            self.video.setVisible(has_video)

        try:
            loaded = os.path.basename(self.mpv.path or "") == os.path.basename(self.path or "")
        except Exception:
            loaded = True
        if not self.restored and dur and loaded:
            try:
                self.mpv.seek(min(self.restore_pos, dur - 1), "absolute")
                self.restored = True
                pos = self.restore_pos
            except Exception:
                pass

        if dur != self.duration:
            self.duration = dur
            self.rebuild_chapters(chs)
        elif [(c.get("time"), c.get("title"), c.get("src")) for c in chs] != \
             [(c.get("time"), c.get("title"), c.get("src")) for c in self.chapters]:
            self.rebuild_chapters(chs)

        if not self.slider.isSliderDown() and dur:
            self.slider.setValue(int(pos / dur * self.slider.maximum()))
        self.lbl_time.setText(f"{fmt(pos)} / {fmt(dur)}")
        if dur:
            self.wave.set_progress(pos / dur)
        self.btn_play.setText("▶" if paused else "⏸")

        if cur is not None and 0 <= cur < self.list.count():
            if self.list.currentRow() != cur:
                self.list.setCurrentRow(cur)
                self.list.scrollToItem(self.list.item(cur), QListWidget.PositionAtCenter)
            title = self.chapters[cur].get("title") or f"Capitol {cur + 1}"
            self.lbl_chapter.setText(title)
        else:
            self.lbl_chapter.setText("")

        self._save_counter += 1
        if self._save_counter >= 8:  # ~2s
            self._save_counter = 0
            self._save_state()

    def closeEvent(self, e):
        self._save_state()
        self.mpv.terminate()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    locale.setlocale(locale.LC_NUMERIC, "C")  # necesar pentru mpv
    w = Player()
    w.show()
    sys.exit(app.exec())
