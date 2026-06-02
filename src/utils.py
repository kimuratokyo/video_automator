"""ユーティリティモジュール

メディアファイル検証、ffprobeラッパー、FFmpegフィルター生成ヘルパーを提供する。
"""

from __future__ import annotations

import json
import subprocess
import shutil
from pathlib import Path


# 対応拡張子
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"}
SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS

# FFmpegトランジション名マッピング
TRANSITION_MAP = {
    "None": None,
    "Fade": "fade",
    "Wipe": "wipeleft",
    "Slide": "slideleft",
}


def is_video(path: str | Path) -> bool:
    """動画ファイルかどうかを判定する。"""
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def is_image(path: str | Path) -> bool:
    """画像ファイルかどうかを判定する。"""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def is_valid_media(path: str | Path) -> bool:
    """対応するメディアファイルかどうかを検証する。"""
    p = Path(path)
    return p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS


def is_valid_audio(path: str | Path) -> bool:
    """対応する音声ファイルかどうかを検証する。"""
    p = Path(path)
    return p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS


def get_ffmpeg_path() -> str:
    """FFmpegの実行パスを取得する。"""
    path = shutil.which("ffmpeg")
    if path is None:
        raise FileNotFoundError(
            "FFmpegが見つかりません。環境変数PATHにFFmpegを追加してください。"
        )
    return path


def get_ffprobe_path() -> str:
    """FFprobeの実行パスを取得する。"""
    path = shutil.which("ffprobe")
    if path is None:
        raise FileNotFoundError(
            "FFprobeが見つかりません。環境変数PATHにFFprobeを追加してください。"
        )
    return path


def get_media_duration(path: str | Path) -> float:
    """ffprobeを使って動画/音声の長さ（秒）を取得する。

    画像の場合は0.0を返す。
    """
    p = Path(path)
    if is_image(p):
        return 0.0

    try:
        ffprobe = get_ffprobe_path()
        result = subprocess.run(
            [
                ffprobe,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(p),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (KeyError, json.JSONDecodeError, ValueError, OSError):
        return 0.0


def has_audio_stream(path: str | Path) -> bool:
    """動画ファイルに音声ストリームが含まれるか確認する。"""
    try:
        ffprobe = get_ffprobe_path()
        result = subprocess.run(
            [
                ffprobe,
                "-v", "quiet",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-print_format", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        return len(streams) > 0
    except (json.JSONDecodeError, OSError):
        return False


def detect_nvenc_support() -> bool:
    """h264_nvencエンコーダーが利用可能か検出する。"""
    try:
        ffmpeg = get_ffmpeg_path()
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return "h264_nvenc" in result.stdout
    except OSError:
        return False


def normalize_filter(
    input_label: str,
    output_label: str,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> str:
    """各入力動画を正規化するフィルター文字列を生成する。

    scale + pad + setsar + fps + format で全入力を統一する。
    """
    return (
        f"{input_label}scale={width}:{height}"
        f":force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={fps},format=yuv420p{output_label}"
    )


def build_xfade_chain(
    durations: list[float],
    transition_type: str = "fade",
    transition_duration: float = 1.0,
) -> tuple[str, str]:
    """複数動画のxfadeフィルターチェーンを生成する。

    Args:
        durations: 各（正規化済み）動画の長さ（秒）のリスト
        transition_type: FFmpegのトランジション名
        transition_duration: トランジション秒数

    Returns:
        (filter文字列, 最終出力ラベル)
    """
    n = len(durations)
    if n < 2:
        raise ValueError("xfadeには2つ以上の入力が必要です")

    filters = []
    cumulative = durations[0]

    for i in range(1, n):
        offset = cumulative - transition_duration
        if offset < 0:
            offset = 0

        # 入力ラベル
        if i == 1:
            vin1 = "[norm0]"
        else:
            vin1 = f"[vx{i - 1}]"

        vin2 = f"[norm{i}]"

        # 最終出力かどうか
        if i == n - 1:
            vout = "[vout]"
        else:
            vout = f"[vx{i}]"

        filters.append(
            f"{vin1}{vin2}xfade=transition={transition_type}"
            f":duration={transition_duration}:offset={offset}{vout}"
        )

        cumulative = offset + durations[i]

    return ";\n".join(filters), "[vout]"


def build_acrossfade_chain(
    count: int,
    transition_duration: float = 1.0,
) -> tuple[str, str]:
    """音声のacrossfadeチェーンを生成する。

    Args:
        count: 入力音声ストリームの数
        transition_duration: クロスフェード秒数

    Returns:
        (filter文字列, 最終出力ラベル)
    """
    if count < 2:
        return "", "[0:a]"

    filters = []
    for i in range(1, count):
        if i == 1:
            ain1 = "[a0]"
        else:
            ain1 = f"[ax{i - 1}]"

        ain2 = f"[a{i}]"

        if i == count - 1:
            aout = "[aout]"
        else:
            aout = f"[ax{i}]"

        filters.append(
            f"{ain1}{ain2}acrossfade=d={transition_duration}{aout}"
        )

    return ";\n".join(filters), "[aout]"
