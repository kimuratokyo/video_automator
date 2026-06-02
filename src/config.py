"""設定管理モジュール

JSON形式での設定の永続化とデフォルト値の管理を行う。
保存先: ~/.video_automator/config.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# デフォルト設定値
DEFAULT_CONFIG: dict[str, Any] = {
    "encoder": "cpu",           # "gpu" or "cpu"
    "image_duration": 5.0,      # 画像の表示秒数
    "transition": "None",       # トランジション種類
    "transition_duration": 1.0, # トランジション秒数
    "audio_mode": "original",   # "original", "bgm_only", "mix"
    "bgm_loop": True,           # BGMループ
    "last_output_dir": "",      # 最後の出力ディレクトリ
    "window_geometry": {
        "x": 100,
        "y": 100,
        "width": 1100,
        "height": 750,
    },
}

CONFIG_DIR = Path.home() / ".video_automator"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict[str, Any]:
    """設定ファイルを読み込む。存在しない場合はデフォルト値を返す。"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # デフォルト値をベースに、保存済みの値で上書き
            config = DEFAULT_CONFIG.copy()
            config.update(saved)
            return config
        except (json.JSONDecodeError, OSError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict[str, Any]) -> None:
    """設定をJSONファイルに保存する。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
