"""FFmpegエンジンモジュール

FFmpegコマンドの構築とQThreadベースの非同期プロセス実行を提供する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from utils import (
    TRANSITION_MAP,
    build_acrossfade_chain,
    build_xfade_chain,
    get_ffmpeg_path,
    get_media_duration,
    has_audio_stream,
    is_image,
    normalize_filter,
)


class FFmpegWorker(QThread):
    """FFmpegプロセスをバックグラウンドで実行するワーカースレッド。

    Signals:
        log_signal(str): ログ行の通知
        progress_signal(int): 進捗率（0-100）の通知
        finished_signal(bool, str): 完了通知（成功?, メッセージ）
    """

    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(bool, str)

    def __init__(
        self,
        cmd: list[str],
        total_duration: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.cmd = cmd
        self.total_duration = total_duration
        self._is_cancelled = False
        self._process: subprocess.Popen | None = None

    def run(self):
        """FFmpegプロセスを実行し、stderrをリアルタイムで読み取る。"""
        try:
            self.log_signal.emit("FFmpegプロセスを開始します...")
            self.log_signal.emit(f"コマンド: {' '.join(self.cmd[:6])}...")

            self._process = subprocess.Popen(
                self.cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            with self._process.stderr:
                for line in iter(self._process.stderr.readline, ""):
                    if self._is_cancelled:
                        self._process.terminate()
                        self.finished_signal.emit(False, "処理がキャンセルされました。")
                        return
                    line = line.strip()
                    if line:
                        self.log_signal.emit(line)
                        # 進捗パース (FFmpegの time= 出力から)
                        self._parse_progress(line)

            self._process.wait()
            rc = self._process.returncode

            if rc == 0:
                self.progress_signal.emit(100)
                self.finished_signal.emit(True, "動画の生成が完了しました！")
            else:
                self.finished_signal.emit(
                    False, f"FFmpegがエラーコード {rc} で終了しました。"
                )
        except FileNotFoundError:
            self.finished_signal.emit(
                False, "FFmpegが見つかりません。PATHを確認してください。"
            )
        except Exception as e:
            self.finished_signal.emit(False, f"予期しないエラー: {e}")

    def _parse_progress(self, line: str):
        """FFmpegのstderr出力から進捗率を計算する。"""
        if self.total_duration <= 0:
            return
        # FFmpegは "time=HH:MM:SS.ss" 形式で進捗を出力する
        if "time=" not in line:
            return
        try:
            time_part = line.split("time=")[1].split()[0]
            # 負の時間(N/A)を除外
            if time_part.startswith("-") or time_part.startswith("N"):
                return
            parts = time_part.split(":")
            seconds = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            progress = min(int((seconds / self.total_duration) * 100), 99)
            self.progress_signal.emit(progress)
        except (IndexError, ValueError):
            pass

    def cancel(self):
        """処理をキャンセルする。"""
        self._is_cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()


def build_ffmpeg_command(
    file_paths: list[str],
    output_path: str,
    transition: str = "None",
    transition_duration: float = 1.0,
    image_duration: float = 5.0,
    audio_mode: str = "original",
    bgm_path: str | None = None,
    bgm_loop: bool = True,
    encoder: str = "cpu",
) -> tuple[list[str], float]:
    """FFmpegコマンドを構築する。

    Args:
        file_paths: 入力ファイルの絶対パスリスト
        output_path: 出力ファイルパス
        transition: トランジション種類
        transition_duration: トランジション秒数
        image_duration: 画像の表示秒数
        audio_mode: 音声モード ("original", "bgm_only", "mix")
        bgm_path: BGMファイルパス
        bgm_loop: BGMをループするか
        encoder: エンコーダー ("gpu" or "cpu")

    Returns:
        (コマンドリスト, 合計出力時間（秒）)
    """
    ffmpeg = get_ffmpeg_path()
    transition_name = TRANSITION_MAP.get(transition)
    n = len(file_paths)

    # --- 入力引数の構築 ---
    input_args: list[str] = []
    durations: list[float] = []

    for path in file_paths:
        if is_image(path):
            # 画像は -loop 1 -t duration で動画化
            input_args.extend(["-loop", "1", "-t", str(image_duration), "-i", str(path)])
            durations.append(image_duration)
        else:
            dur = get_media_duration(path)
            if dur <= 0:
                dur = 10.0  # フォールバック
            input_args.extend(["-i", str(path)])
            durations.append(dur)

    # BGM入力
    bgm_input_index = None
    if bgm_path and (audio_mode in ("bgm_only", "mix")):
        if bgm_loop:
            input_args.extend(["-stream_loop", "-1"])
        input_args.extend(["-i", str(bgm_path)])
        bgm_input_index = n  # BGMの入力インデックス

    # --- フィルター構築 ---
    filter_parts: list[str] = []

    # 1. 各入力の正規化フィルター
    for i in range(n):
        filter_parts.append(normalize_filter(f"[{i}:v]", f"[norm{i}]"))

    # 2. 映像結合
    if n == 1:
        # 素材が1つの場合はそのまま
        final_video_label = "[norm0]"
    elif transition_name and n >= 2:
        # xfadeトランジション付き結合
        xfade_filter, final_video_label = build_xfade_chain(
            durations, transition_name, transition_duration
        )
        filter_parts.append(xfade_filter)
    else:
        # トランジションなし: concat フィルター使用
        concat_inputs = "".join(f"[norm{i}]" for i in range(n))
        filter_parts.append(
            f"{concat_inputs}concat=n={n}:v=1:a=0[vout]"
        )
        final_video_label = "[vout]"

    # 3. 音声処理
    final_audio_label = None
    use_audio = False

    if audio_mode == "original":
        # 素材の音声を結合
        audio_sources: list[int] = []
        for i in range(n):
            if is_image(file_paths[i]):
                # 画像用の無音トラック生成
                filter_parts.append(
                    f"anullsrc=channel_layout=stereo:sample_rate=44100[a{i}]"
                )
                # 長さは trim で制限
                filter_parts.append(
                    f"[a{i}]atrim=0:{durations[i]}[at{i}]"
                )
                audio_sources.append(i)
            elif has_audio_stream(file_paths[i]):
                filter_parts.append(f"[{i}:a]acopy[at{i}]")
                audio_sources.append(i)
            else:
                # 音声なし動画 → 無音
                filter_parts.append(
                    f"anullsrc=channel_layout=stereo:sample_rate=44100[a{i}]"
                )
                filter_parts.append(
                    f"[a{i}]atrim=0:{durations[i]}[at{i}]"
                )
                audio_sources.append(i)

        if len(audio_sources) >= 2 and transition_name:
            # acrossfade チェーン
            # ラベルをリネーム
            for idx, i in enumerate(audio_sources):
                filter_parts.append(f"[at{i}]acopy[af{idx}]")

            acf_filter, final_audio_label = build_acrossfade_chain(
                len(audio_sources), transition_duration
            )
            # ラベルを修正 (af0, af1, ... に合わせる)
            acf_filter = acf_filter.replace("[a0]", "[af0]")
            for idx in range(1, len(audio_sources)):
                acf_filter = acf_filter.replace(f"[a{idx}]", f"[af{idx}]")
            filter_parts.append(acf_filter)
            use_audio = True
        elif len(audio_sources) >= 1:
            # concat で音声も結合
            concat_a_inputs = "".join(f"[at{i}]" for i in audio_sources)
            filter_parts.append(
                f"{concat_a_inputs}concat=n={len(audio_sources)}:v=0:a=1[aout]"
            )
            final_audio_label = "[aout]"
            use_audio = True

    elif audio_mode == "bgm_only":
        # BGMのみ（素材音声ミュート）
        if bgm_input_index is not None:
            final_audio_label = f"{bgm_input_index}:a"
            use_audio = True

    elif audio_mode == "mix":
        # 素材音声 + BGMミックス
        if bgm_input_index is not None:
            # まず素材音声を結合
            audio_sources_mix: list[int] = []
            for i in range(n):
                if is_image(file_paths[i]):
                    filter_parts.append(
                        f"anullsrc=channel_layout=stereo:sample_rate=44100[am{i}]"
                    )
                    filter_parts.append(
                        f"[am{i}]atrim=0:{durations[i]}[amt{i}]"
                    )
                    audio_sources_mix.append(i)
                elif has_audio_stream(file_paths[i]):
                    filter_parts.append(f"[{i}:a]acopy[amt{i}]")
                    audio_sources_mix.append(i)
                else:
                    filter_parts.append(
                        f"anullsrc=channel_layout=stereo:sample_rate=44100[am{i}]"
                    )
                    filter_parts.append(
                        f"[am{i}]atrim=0:{durations[i]}[amt{i}]"
                    )
                    audio_sources_mix.append(i)

            if audio_sources_mix:
                concat_a = "".join(f"[amt{i}]" for i in audio_sources_mix)
                filter_parts.append(
                    f"{concat_a}concat=n={len(audio_sources_mix)}:v=0:a=1[orig_audio]"
                )
                # BGMとミックス
                filter_parts.append(
                    f"[orig_audio][{bgm_input_index}:a]amix=inputs=2:duration=first[aout]"
                )
                final_audio_label = "[aout]"
                use_audio = True

    # --- コマンド組み立て ---
    cmd = [ffmpeg, "-y"]
    cmd.extend(input_args)

    # フィルター
    filter_complex = ";\n".join(f for f in filter_parts if f)
    cmd.extend(["-filter_complex", filter_complex])

    # マッピング
    cmd.extend(["-map", final_video_label])
    if use_audio and final_audio_label:
        # final_audio_label は "[aout]"（フィルターラベル）か "2:a"（ストリーム指定子）
        # どちらも -map にそのまま渡せる
        cmd.extend(["-map", final_audio_label])

    # エンコーダー設定（Windows標準プレーヤー互換）
    if encoder == "gpu":
        cmd.extend([
            "-c:v", "h264_nvenc",
            "-preset", "p7",
            "-cq", "20",
            "-b:v", "0",
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-level", "4.1",
        ])
    else:
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-level", "4.1",
        ])

    # 音声エンコーダー
    if use_audio or (audio_mode == "bgm_only" and bgm_input_index is not None):
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    # BGMループ時は -shortest
    if bgm_path and bgm_loop and audio_mode in ("bgm_only", "mix"):
        cmd.append("-shortest")

    # MP4互換性: ヘッダーを先頭に配置（Windows再生互換）
    cmd.extend(["-movflags", "+faststart"])

    cmd.append(str(output_path))

    # 合計時間の計算
    if transition_name and n >= 2:
        total_duration = sum(durations) - (n - 1) * transition_duration
    else:
        total_duration = sum(durations)

    return cmd, max(total_duration, 0)
