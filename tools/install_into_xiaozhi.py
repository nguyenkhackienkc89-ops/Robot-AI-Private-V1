#!/usr/bin/env python3
from pathlib import Path
import shutil, sys

if len(sys.argv) != 2:
    raise SystemExit("Dùng: python tools/install_into_xiaozhi.py /path/to/xiaozhi-esp32")

bundle = Path(__file__).resolve().parent.parent
repo = Path(sys.argv[1]).resolve()
if not (repo / "main" / "CMakeLists.txt").exists():
    raise SystemExit("Không phải thư mục xiaozhi-esp32.")

src_board = bundle / "xiaozhi_overlay" / "main" / "boards" / "robot-ai-private-v1"
dst_board = repo / "main" / "boards" / "robot-ai-private-v1"
if dst_board.exists():
    shutil.rmtree(dst_board)
shutil.copytree(src_board, dst_board)

# Kconfig: chèn vào đúng choice BOARD_TYPE.
kconfig = repo / "main" / "Kconfig.projbuild"
text = kconfig.read_text(encoding="utf-8")
if "config BOARD_TYPE_ROBOT_AI_PRIVATE_V1" not in text:
    choice_pos = text.find("choice BOARD_TYPE")
    if choice_pos < 0:
        raise RuntimeError("Không tìm thấy choice BOARD_TYPE")
    endchoice_pos = text.find("endchoice", choice_pos)
    if endchoice_pos < 0:
        raise RuntimeError("Không tìm thấy endchoice của BOARD_TYPE")
    entry = '''\n    config BOARD_TYPE_ROBOT_AI_PRIVATE_V1\n        bool "Robot AI Private V1"\n        depends on IDF_TARGET_ESP32S3\n\n'''
    text = text[:endchoice_pos] + entry + text[endchoice_pos:]
    kconfig.write_text(text, encoding="utf-8")

# CMake: chèn ngay trước branch bread-compact-wifi đầu tiên trong BOARD_DIR chain.
cmake = repo / "main" / "CMakeLists.txt"
text = cmake.read_text(encoding="utf-8")
if 'set(BOARD_DIR "robot-ai-private-v1")' not in text:
    anchor = 'if(CONFIG_BOARD_TYPE_BREAD_COMPACT_WIFI)\n'
    if anchor not in text:
        raise RuntimeError("Không tìm thấy BOARD_DIR chain anchor")
    replacement = '''if(CONFIG_BOARD_TYPE_ROBOT_AI_PRIVATE_V1)\n    set(BOARD_DIR "robot-ai-private-v1")\n    set(BUILTIN_TEXT_FONT font_noto_sans_basic_14_1)\n    set(BUILTIN_ICON_FONT font_material_symbols_14_1)\n    set(DEFAULT_EMOJI_COLLECTION noto-color-emoji_32)\nelseif(CONFIG_BOARD_TYPE_BREAD_COMPACT_WIFI)\n'''
    text = text.replace(anchor, replacement, 1)
    cmake.write_text(text, encoding="utf-8")

# CMake: esp_http_client is used by the private board source, so add it to
# the main component dependency list before idf_component_register() runs.
text = cmake.read_text(encoding="utf-8")
if "esp_http_client" not in text:
    anchor = 'set(MAIN_PRIV_REQUIRES_EXTRA "")\n'
    if anchor not in text:
        raise RuntimeError("Không tìm thấy MAIN_PRIV_REQUIRES_EXTRA trong CMakeLists.txt")
    text = text.replace(
        anchor,
        anchor + "list(APPEND MAIN_PRIV_REQUIRES_EXTRA esp_http_client)\n",
        1,
    )
    cmake.write_text(text, encoding="utf-8")

# Hard verification before build.py runs.
kt = kconfig.read_text(encoding="utf-8")
ct = cmake.read_text(encoding="utf-8")
checks = [
    ('Kconfig symbol', 'config BOARD_TYPE_ROBOT_AI_PRIVATE_V1', kt),
    ('CMake condition', 'CONFIG_BOARD_TYPE_ROBOT_AI_PRIVATE_V1', ct),
    ('CMake board dir', 'set(BOARD_DIR "robot-ai-private-v1")', ct),
    ('CMake esp_http_client dependency', 'esp_http_client', ct),
]
for label, needle, hay in checks:
    if needle not in hay:
        raise RuntimeError(f"{label} verification failed")

print("Robot AI Private V1 board registration: PASS")


# -------------------------------------------------------------------
# V5: Wi-Fi config portal uses XiaoZhi/esp-wifi-connect's real captive
# portal at 192.168.4.1, but with our robot identity instead of Xiaozhi.
# -------------------------------------------------------------------
wifi_board = repo / "main" / "boards" / "common" / "wifi_board.cc"
wifi_text = wifi_board.read_text(encoding="utf-8")
wifi_text = wifi_text.replace(
    'config.ssid_prefix = "Xiaozhi";',
    'config.ssid_prefix = "TieuDe";'
)
wifi_board.write_text(wifi_text, encoding="utf-8")
