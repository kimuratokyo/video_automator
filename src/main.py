"""Video Automator - メインGUIモジュール

PySide6によるメインウィンドウの構築とアプリケーションエントリーポイント。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import load_config, save_config
from engine import FFmpegWorker, build_ffmpeg_command
from utils import (
    SUPPORTED_EXTENSIONS,
    detect_nvenc_support,
    is_valid_audio,
    is_valid_media,
)


# ─── スタイルシート ───────────────────────────────────────

STYLESHEET = """
QMainWindow {
    background-color: #1a1a2e;
}

QWidget {
    color: #e0e0e0;
    font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
    font-size: 13px;
}

/* ─── グループボックス ─── */
QGroupBox {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 8px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: bold;
    font-size: 13px;
    color: #a8d8ea;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: #a8d8ea;
}

/* ─── リストウィジェット ─── */
QListWidget {
    background-color: #0f3460;
    border: 2px dashed #533483;
    border-radius: 8px;
    padding: 8px;
    color: #e0e0e0;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
    margin: 2px 0;
}
QListWidget::item:selected {
    background-color: #533483;
    color: #ffffff;
}
QListWidget::item:hover {
    background-color: #1a1a4e;
}

/* ─── ボタン ─── */
QPushButton {
    background-color: #533483;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: bold;
    font-size: 13px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #6a4c9c;
}
QPushButton:pressed {
    background-color: #3d2266;
}
QPushButton:disabled {
    background-color: #2a2a4a;
    color: #666688;
}

QPushButton#btn_generate {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e94560, stop:1 #c23152);
    font-size: 15px;
    padding: 12px 24px;
    min-height: 36px;
}
QPushButton#btn_generate:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ff5a7a, stop:1 #d94060);
}
QPushButton#btn_generate:disabled {
    background: #3a2a3e;
    color: #666688;
}

QPushButton#btn_cancel {
    background-color: #c23152;
}
QPushButton#btn_cancel:hover {
    background-color: #e94560;
}

QPushButton#btn_small {
    padding: 4px 10px;
    min-height: 22px;
    font-size: 12px;
}

/* ─── コンボボックス ─── */
QComboBox {
    background-color: #0f3460;
    border: 1px solid #533483;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e0e0;
    min-height: 24px;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 1px solid #533483;
    selection-background-color: #533483;
    color: #e0e0e0;
}

/* ─── スピンボックス ─── */
QDoubleSpinBox {
    background-color: #0f3460;
    border: 1px solid #533483;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e0e0;
    min-height: 24px;
}

/* ─── チェックボックス & ラジオボタン ─── */
QCheckBox, QRadioButton {
    spacing: 8px;
    color: #e0e0e0;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}

/* ─── テキストエリア（ログ） ─── */
QTextEdit#log_area {
    background-color: #0a0a1a;
    border: 1px solid #1a1a3e;
    border-radius: 6px;
    padding: 8px;
    color: #88cc88;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
}

/* ─── プログレスバー ─── */
QProgressBar {
    background-color: #0f3460;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #e0e0e0;
    min-height: 20px;
    font-size: 11px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e94560, stop:0.5 #533483, stop:1 #0f3460);
    border-radius: 4px;
}

/* ─── ラベル ─── */
QLabel {
    color: #c0c0d0;
    font-size: 12px;
}
QLabel#title_label {
    color: #a8d8ea;
    font-size: 14px;
    font-weight: bold;
}
QLabel#drop_hint {
    color: #666688;
    font-size: 16px;
    font-style: italic;
}
QLabel#bgm_label {
    color: #88aa88;
    font-size: 11px;
}

/* ─── スプリッター ─── */
QSplitter::handle {
    background-color: #533483;
    height: 3px;
}
"""


class MediaListWidget(QListWidget):
    """外部ファイルのD&Dと内部並べ替えに対応したリストウィジェット。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path and is_valid_media(file_path):
                    self._add_media_item(file_path)
                elif file_path and Path(file_path).is_dir():
                    self._add_directory(file_path)
            event.accept()
        else:
            super().dropEvent(event)

    def _add_media_item(self, file_path: str):
        """メディアファイルをリストに追加する。"""
        item = QListWidgetItem(Path(file_path).name)
        item.setData(Qt.ItemDataRole.UserRole, file_path)
        item.setToolTip(file_path)
        self.addItem(item)

    def _add_directory(self, dir_path: str):
        """ディレクトリ内の対応ファイルを再帰的に追加する。"""
        for p in sorted(Path(dir_path).rglob("*")):
            if is_valid_media(p):
                self._add_media_item(str(p))


class MainWindow(QMainWindow):
    """Video Automator メインウィンドウ。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Automator")
        self.setMinimumSize(900, 600)

        self._worker: FFmpegWorker | None = None
        self._nvenc_available = detect_nvenc_support()
        self._config = load_config()

        self._setup_ui()
        self._connect_signals()
        self._restore_config()

    # ─── UI構築 ─────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # ── ヘッダー ──
        header = QHBoxLayout()
        title = QLabel("🎬 Video Automator")
        title.setObjectName("title_label")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        main_layout.addLayout(header)

        # ── 上部: リスト + 設定 ──
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左側: 素材リスト
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_group = QGroupBox("素材リスト")
        list_inner = QVBoxLayout(list_group)

        self.media_list = MediaListWidget()
        self.media_list.setMinimumHeight(280)
        drop_hint = QLabel("📁 ファイル/フォルダをここにドラッグ＆ドロップ")
        drop_hint.setObjectName("drop_hint")
        drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        list_inner.addWidget(drop_hint)
        list_inner.addWidget(self.media_list, 1)

        # リスト操作ボタン
        list_buttons = QHBoxLayout()

        self.btn_add = QPushButton("＋ 追加")
        self.btn_add.setObjectName("btn_small")

        self.btn_move_up = QPushButton("▲")
        self.btn_move_up.setObjectName("btn_small")
        self.btn_move_up.setMaximumWidth(40)

        self.btn_move_down = QPushButton("▼")
        self.btn_move_down.setObjectName("btn_small")
        self.btn_move_down.setMaximumWidth(40)

        self.btn_remove = QPushButton("🗑 削除")
        self.btn_remove.setObjectName("btn_small")

        self.btn_clear = QPushButton("全消去")
        self.btn_clear.setObjectName("btn_small")

        list_buttons.addWidget(self.btn_add)
        list_buttons.addWidget(self.btn_move_up)
        list_buttons.addWidget(self.btn_move_down)
        list_buttons.addStretch()
        list_buttons.addWidget(self.btn_remove)
        list_buttons.addWidget(self.btn_clear)

        list_inner.addLayout(list_buttons)
        left_layout.addWidget(list_group)

        # 右側: 設定パネル
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # -- トランジション設定 --
        transition_group = QGroupBox("トランジション")
        transition_inner = QVBoxLayout(transition_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("効果:"))
        self.combo_transition = QComboBox()
        self.combo_transition.addItems(["None", "Fade", "Wipe", "Slide"])
        row1.addWidget(self.combo_transition, 1)
        transition_inner.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("秒数:"))
        self.spin_transition_dur = QDoubleSpinBox()
        self.spin_transition_dur.setRange(0.1, 5.0)
        self.spin_transition_dur.setValue(1.0)
        self.spin_transition_dur.setSingleStep(0.1)
        self.spin_transition_dur.setSuffix(" 秒")
        row2.addWidget(self.spin_transition_dur, 1)
        transition_inner.addLayout(row2)

        right_layout.addWidget(transition_group)

        # -- 画像設定 --
        image_group = QGroupBox("画像設定")
        image_inner = QVBoxLayout(image_group)

        row_img = QHBoxLayout()
        row_img.addWidget(QLabel("表示時間:"))
        self.spin_image_dur = QDoubleSpinBox()
        self.spin_image_dur.setRange(1.0, 30.0)
        self.spin_image_dur.setValue(5.0)
        self.spin_image_dur.setSingleStep(0.5)
        self.spin_image_dur.setSuffix(" 秒")
        row_img.addWidget(self.spin_image_dur, 1)
        image_inner.addLayout(row_img)

        right_layout.addWidget(image_group)

        # -- 音声設定 --
        audio_group = QGroupBox("音声設定")
        audio_inner = QVBoxLayout(audio_group)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("モード:"))
        self.combo_audio_mode = QComboBox()
        self.combo_audio_mode.addItems([
            "素材の音声をそのまま結合",
            "BGMのみ使用",
            "素材音声 + BGMをミックス",
        ])
        row_mode.addWidget(self.combo_audio_mode, 1)
        audio_inner.addLayout(row_mode)

        row_bgm = QHBoxLayout()
        self.btn_bgm = QPushButton("🎵 BGM選択")
        self.btn_bgm.setObjectName("btn_small")
        self.bgm_label = QLabel("未選択")
        self.bgm_label.setObjectName("bgm_label")
        row_bgm.addWidget(self.btn_bgm)
        row_bgm.addWidget(self.bgm_label, 1)
        audio_inner.addLayout(row_bgm)

        self.chk_bgm_loop = QCheckBox("BGMをループ再生")
        self.chk_bgm_loop.setChecked(True)
        audio_inner.addWidget(self.chk_bgm_loop)

        right_layout.addWidget(audio_group)

        # -- エンコーダー設定 --
        encoder_group = QGroupBox("エンコーダー")
        encoder_inner = QVBoxLayout(encoder_group)

        self.radio_gpu = QRadioButton("GPU (h264_nvenc)")
        self.radio_cpu = QRadioButton("CPU (libx264)")
        self.radio_cpu.setChecked(True)

        if not self._nvenc_available:
            self.radio_gpu.setEnabled(False)
            self.radio_gpu.setText("GPU (h264_nvenc) — 利用不可")

        self.encoder_group = QButtonGroup(self)
        self.encoder_group.addButton(self.radio_gpu, 0)
        self.encoder_group.addButton(self.radio_cpu, 1)

        encoder_inner.addWidget(self.radio_gpu)
        encoder_inner.addWidget(self.radio_cpu)

        right_layout.addWidget(encoder_group)

        # -- 生成ボタン --
        right_layout.addStretch()

        self.btn_generate = QPushButton("🎬 動画を生成")
        self.btn_generate.setObjectName("btn_generate")
        right_layout.addWidget(self.btn_generate)

        self.btn_cancel = QPushButton("⏹ キャンセル")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setVisible(False)
        right_layout.addWidget(self.btn_cancel)

        # スプリッターに追加
        top_splitter.addWidget(left_panel)
        top_splitter.addWidget(right_panel)
        top_splitter.setStretchFactor(0, 3)
        top_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(top_splitter, 1)

        # ── 下部: ログ + プログレス ──
        log_group = QGroupBox("処理ログ")
        log_inner = QVBoxLayout(log_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        log_inner.addWidget(self.progress_bar)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("log_area")
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(180)
        self.log_area.setPlaceholderText("ここにFFmpegの処理ログが表示されます...")
        log_inner.addWidget(self.log_area)

        main_layout.addWidget(log_group)

        # ウィンドウサイズ復元
        geom = self._config.get("window_geometry", {})
        self.resize(geom.get("width", 1100), geom.get("height", 750))
        if geom.get("x") and geom.get("y"):
            self.move(geom["x"], geom["y"])

    # ─── Signal/Slot接続 ────────────────────────────────

    def _connect_signals(self):
        self.btn_add.clicked.connect(self._on_add_files)
        self.btn_move_up.clicked.connect(self._on_move_up)
        self.btn_move_down.clicked.connect(self._on_move_down)
        self.btn_remove.clicked.connect(self._on_remove_item)
        self.btn_clear.clicked.connect(self._on_clear_list)
        self.btn_bgm.clicked.connect(self._on_select_bgm)
        self.btn_generate.clicked.connect(self._on_generate)
        self.btn_cancel.clicked.connect(self._on_cancel)

    # ─── 設定の復元・保存 ────────────────────────────────

    def _restore_config(self):
        """前回の設定を復元する。"""
        cfg = self._config
        # トランジション
        idx = self.combo_transition.findText(cfg.get("transition", "None"))
        if idx >= 0:
            self.combo_transition.setCurrentIndex(idx)
        self.spin_transition_dur.setValue(cfg.get("transition_duration", 1.0))
        # 画像表示時間
        self.spin_image_dur.setValue(cfg.get("image_duration", 5.0))
        # 音声モード
        audio_map = {"original": 0, "bgm_only": 1, "mix": 2}
        self.combo_audio_mode.setCurrentIndex(
            audio_map.get(cfg.get("audio_mode", "original"), 0)
        )
        # BGMループ
        self.chk_bgm_loop.setChecked(cfg.get("bgm_loop", True))
        # エンコーダー
        if cfg.get("encoder") == "gpu" and self._nvenc_available:
            self.radio_gpu.setChecked(True)
        else:
            self.radio_cpu.setChecked(True)

    def _save_current_config(self):
        """現在の設定を保存する。"""
        audio_modes = ["original", "bgm_only", "mix"]
        self._config.update({
            "transition": self.combo_transition.currentText(),
            "transition_duration": self.spin_transition_dur.value(),
            "image_duration": self.spin_image_dur.value(),
            "audio_mode": audio_modes[self.combo_audio_mode.currentIndex()],
            "bgm_loop": self.chk_bgm_loop.isChecked(),
            "encoder": "gpu" if self.radio_gpu.isChecked() else "cpu",
            "window_geometry": {
                "x": self.x(),
                "y": self.y(),
                "width": self.width(),
                "height": self.height(),
            },
        })
        save_config(self._config)

    def closeEvent(self, event):
        """ウィンドウ閉じる時に設定を保存。"""
        self._save_current_config()
        if self._worker and self._worker.isRunning():
            reply = QMessageBox.question(
                self,
                "確認",
                "処理中です。終了しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self._worker.cancel()
            self._worker.wait(3000)
        event.accept()

    # ─── スロット: リスト操作 ───────────────────────────

    @Slot()
    def _on_add_files(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "メディアファイルを選択",
            self._config.get("last_output_dir", ""),
            f"メディアファイル ({exts});;すべてのファイル (*)",
        )
        for f in files:
            if is_valid_media(f):
                item = QListWidgetItem(Path(f).name)
                item.setData(Qt.ItemDataRole.UserRole, f)
                item.setToolTip(f)
                self.media_list.addItem(item)

    @Slot()
    def _on_move_up(self):
        row = self.media_list.currentRow()
        if row > 0:
            item = self.media_list.takeItem(row)
            self.media_list.insertItem(row - 1, item)
            self.media_list.setCurrentRow(row - 1)

    @Slot()
    def _on_move_down(self):
        row = self.media_list.currentRow()
        if row < self.media_list.count() - 1:
            item = self.media_list.takeItem(row)
            self.media_list.insertItem(row + 1, item)
            self.media_list.setCurrentRow(row + 1)

    @Slot()
    def _on_remove_item(self):
        row = self.media_list.currentRow()
        if row >= 0:
            self.media_list.takeItem(row)

    @Slot()
    def _on_clear_list(self):
        if self.media_list.count() == 0:
            return
        reply = QMessageBox.question(
            self,
            "確認",
            "リストをすべて消去しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.media_list.clear()

    # ─── スロット: BGM選択 ──────────────────────────────

    @Slot()
    def _on_select_bgm(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "BGMファイルを選択",
            "",
            "音声ファイル (*.mp3 *.wav *.aac *.flac *.ogg *.m4a);;すべてのファイル (*)",
        )
        if file and is_valid_audio(file):
            self._bgm_path = file
            self.bgm_label.setText(Path(file).name)
            self.bgm_label.setToolTip(file)
        elif file:
            QMessageBox.warning(self, "エラー", "対応していない音声形式です。")

    # ─── スロット: 生成 ────────────────────────────────

    @Slot()
    def _on_generate(self):
        # バリデーション
        if self.media_list.count() == 0:
            QMessageBox.warning(self, "エラー", "素材がありません。\nファイルを追加してください。")
            return

        # ファイルパスの収集
        file_paths: list[str] = []
        for i in range(self.media_list.count()):
            item = self.media_list.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            if not Path(path).exists():
                QMessageBox.warning(
                    self,
                    "無効なパス",
                    f"ファイルが見つかりません:\n{path}",
                )
                return
            file_paths.append(path)

        # 重複チェック
        if len(file_paths) != len(set(file_paths)):
            reply = QMessageBox.question(
                self,
                "警告",
                "重複するファイルがあります。続行しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # 音声モードとBGMの検証
        audio_modes = ["original", "bgm_only", "mix"]
        audio_mode = audio_modes[self.combo_audio_mode.currentIndex()]
        bgm_path = getattr(self, "_bgm_path", None)

        if audio_mode in ("bgm_only", "mix") and not bgm_path:
            QMessageBox.warning(
                self,
                "BGM未選択",
                "BGMを使用するモードが選択されていますが、BGMファイルが選択されていません。",
            )
            return

        # 出力先の選択
        default_dir = self._config.get("last_output_dir", "")
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "出力先を指定",
            os.path.join(default_dir, "output.mp4") if default_dir else "output.mp4",
            "MP4ファイル (*.mp4);;すべてのファイル (*)",
        )
        if not output_path:
            return

        # 出力ディレクトリを記憶
        self._config["last_output_dir"] = str(Path(output_path).parent)

        # パラメータ収集
        transition = self.combo_transition.currentText()
        transition_duration = self.spin_transition_dur.value()
        image_duration = self.spin_image_dur.value()
        bgm_loop = self.chk_bgm_loop.isChecked()
        encoder = "gpu" if self.radio_gpu.isChecked() else "cpu"

        # コマンド構築
        try:
            cmd, total_duration = build_ffmpeg_command(
                file_paths=file_paths,
                output_path=output_path,
                transition=transition,
                transition_duration=transition_duration,
                image_duration=image_duration,
                audio_mode=audio_mode,
                bgm_path=bgm_path,
                bgm_loop=bgm_loop,
                encoder=encoder,
            )
        except Exception as e:
            QMessageBox.critical(self, "コマンド構築エラー", str(e))
            return

        # UI状態更新
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.btn_generate.setEnabled(False)
        self.btn_generate.setVisible(False)
        self.btn_cancel.setVisible(True)

        self._output_path = output_path

        # ワーカー起動
        self._worker = FFmpegWorker(cmd, total_duration)
        self._worker.log_signal.connect(self._on_log)
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

        self.log_area.append("🚀 動画生成を開始しました...")

    @Slot()
    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.log_area.append("⏹ キャンセルを要求しました...")

    @Slot(str)
    def _on_log(self, text: str):
        self.log_area.append(text)
        # 自動スクロール
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(int)
    def _on_progress(self, value: int):
        self.progress_bar.setValue(value)

    @Slot(bool, str)
    def _on_finished(self, success: bool, message: str):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setVisible(True)
        self.btn_cancel.setVisible(False)

        if success:
            self.log_area.append(f"\n✅ {message}")
            self.progress_bar.setValue(100)
            self._save_current_config()

            reply = QMessageBox.information(
                self,
                "完了",
                f"{message}\n\n保存先フォルダを開きますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                output_dir = str(Path(self._output_path).parent)
                os.startfile(output_dir)
        else:
            self.log_area.append(f"\n❌ {message}")
            QMessageBox.critical(self, "エラー", message)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
