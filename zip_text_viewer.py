import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QAction, QKeySequence, QTextCursor, QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QListWidget, QTextEdit,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
    QComboBox, QSplitter, QSizePolicy, QCheckBox
)

TEXT_EXTS = {".txt", ".md", ".log", ".csv", ".json", ".tsv", ".yaml", ".yml", ".ini", ".cfg"}
PREVIEW_MAX_BYTES = 10 * 1024 * 1024  # 10MB

# 줄바꿈 권장 규칙:
# - 일반 문서/텍스트: ON 권장
# - 로그/코드/데이터: OFF 권장(가로 정렬 유지가 중요)
WRAP_RECOMMEND_OFF = {".log", ".json", ".csv", ".tsv", ".ini", ".cfg", ".yaml", ".yml"}
WRAP_RECOMMEND_ON = {".txt", ".md"}


@dataclass
class EntryInfo:
    name: str
    size: int  # uncompressed size


def is_text_candidate(filename: str) -> bool:
    return Path(filename).suffix.lower() in TEXT_EXTS


def get_ext(filename: str) -> str:
    return Path(filename).suffix.lower()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZIP 텍스트 뷰어 (UTF-8/CP949)")

        self.zip_path: Path | None = None
        self.zf: zipfile.ZipFile | None = None
        self.entries: list[EntryInfo] = []
        self.current_entry: EntryInfo | None = None
        self.last_raw_bytes: bytes | None = None

        # 사용자가 토글을 수동으로 바꿨는지 여부 (자동 권장과 충돌 방지)
        self.user_overrode_wrap_for_current = False

        # --- 메뉴 ---
        open_act = QAction("ZIP 열기", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self.open_zip)

        exit_act = QAction("종료", self)
        exit_act.setShortcut(QKeySequence.Quit)
        exit_act.triggered.connect(self.close)

        file_menu = self.menuBar().addMenu("파일")
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        file_menu.addAction(exit_act)

        # Ctrl+F (찾기 창 포커스)
        find_act = QAction("찾기", self)
        find_act.setShortcut(QKeySequence.Find)
        find_act.triggered.connect(self.focus_search)
        self.addAction(find_act)

        # --- 레이아웃 ---
        root = QWidget()
        self.setCentralWidget(root)

        splitter = QSplitter(Qt.Horizontal)

        # Left
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.zip_label = QLabel("ZIP: (열지 않음)")
        self.zip_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        left_layout.addWidget(self.zip_label)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("필터(파일명 검색) 예: log, 2025, chapter ...")
        self.filter_edit.textChanged.connect(self.apply_filter)
        left_layout.addWidget(self.filter_edit)

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_select_entry)
        left_layout.addWidget(self.list_widget)

        # Right
        right = QWidget()
        right_layout = QVBoxLayout(right)

        top_bar = QHBoxLayout()

        self.entry_label = QLabel("파일: -")
        self.entry_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.entry_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_bar.addWidget(self.entry_label)

        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["자동(UTF-8 우선)", "UTF-8", "CP949"])
        self.encoding_combo.currentIndexChanged.connect(self.redecode_current)
        top_bar.addWidget(QLabel("인코딩:"))
        top_bar.addWidget(self.encoding_combo)

        # ✅ 자동 권장 적용 체크박스
        self.auto_wrap_check = QCheckBox("확장자 기반 줄바꿈 권장 적용")
        self.auto_wrap_check.setChecked(True)
        self.auto_wrap_check.stateChanged.connect(self.on_auto_wrap_changed)
        top_bar.addWidget(self.auto_wrap_check)

        # ✅ 줄바꿈 토글 버튼(수동)
        self.wrap_btn = QPushButton("줄바꿈: ON")
        self.wrap_btn.setCheckable(True)
        self.wrap_btn.setChecked(True)  # 기본 ON(문서 읽기 기준)
        self.wrap_btn.toggled.connect(self.on_user_toggle_wrap)
        top_bar.addWidget(self.wrap_btn)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("검색 (Enter: 다음 / Shift+Enter: 이전)")
        self.search_edit.returnPressed.connect(self.search_next)
        self.search_edit.installEventFilter(self)  # Shift+Enter 처리
        top_bar.addWidget(self.search_edit)

        btn_prev = QPushButton("이전")
        btn_prev.clicked.connect(lambda: self.search_next(backward=True))
        top_bar.addWidget(btn_prev)

        btn_next = QPushButton("다음")
        btn_next.clicked.connect(self.search_next)
        top_bar.addWidget(btn_next)

        right_layout.addLayout(top_bar)

        self.text = QTextEdit()
        self.text.setReadOnly(True)

        # 기본: 줄바꿈 ON + (가능하면 단어 단위, 아니면 어디서든) 줄바꿈
        self.apply_wrap(True)

        right_layout.addWidget(self.text)

        self.status = QLabel("")
        right_layout.addWidget(self.status)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(root)
        layout.addWidget(splitter)

    # Shift+Enter(이전 찾기)
    def eventFilter(self, obj, event):
        if obj is self.search_edit and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ShiftModifier):
                self.search_next(backward=True)
                return True
        return super().eventFilter(obj, event)

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # --- 줄바꿈 제어 ---
    def apply_wrap(self, enabled: bool):
        """실제로 QTextEdit에 적용"""
        if enabled:
            self.text.setLineWrapMode(QTextEdit.WidgetWidth)
            # ✅ 핵심 수정:
            # 공백/단어 경계가 있으면 단어 단위로, 없으면(토큰/URL/언더스코어 등) 아무 지점에서도 줄바꿈 허용
            self.text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            self.wrap_btn.setText("줄바꿈: ON")
        else:
            self.text.setLineWrapMode(QTextEdit.NoWrap)
            self.wrap_btn.setText("줄바꿈: OFF")

        # 버튼 상태를 프로그램적으로 맞추되, '사용자 override' 플래그를 건드리지 않기 위해 signals 차단
        self.wrap_btn.blockSignals(True)
        self.wrap_btn.setChecked(enabled)
        self.wrap_btn.blockSignals(False)

    def recommend_wrap_for_entry(self, filename: str) -> bool:
        """확장자 기반 권장값"""
        ext = get_ext(filename)
        if ext in WRAP_RECOMMEND_OFF:
            return False
        if ext in WRAP_RECOMMEND_ON:
            return True
        # 그 외 텍스트 후보는 기본 ON (읽기 중심)
        return True

    def apply_recommended_wrap_if_needed(self, filename: str):
        """자동 권장 모드일 때, 현재 파일에 대해 권장 줄바꿈을 적용"""
        if not self.auto_wrap_check.isChecked():
            return
        # 사용자가 이 파일에서 수동으로 바꿨다면 자동이 덮어쓰지 않도록
        if self.user_overrode_wrap_for_current:
            return

        rec = self.recommend_wrap_for_entry(filename)
        self.apply_wrap(rec)
        self.status.setText(self.status.text() + f" | 줄바꿈 권장: {'ON' if rec else 'OFF'}")

    def on_user_toggle_wrap(self, checked: bool):
        """사용자가 직접 토글한 경우"""
        self.user_overrode_wrap_for_current = True
        self.apply_wrap(checked)

    def on_auto_wrap_changed(self):
        """자동 권장 체크박스를 켜면, 현재 파일 기준으로 다시 권장 적용"""
        if self.auto_wrap_check.isChecked() and self.current_entry is not None:
            self.user_overrode_wrap_for_current = False
            self.apply_recommended_wrap_if_needed(self.current_entry.name)

    # --- ZIP 로드 ---
    def open_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "ZIP 파일 선택", "", "ZIP files (*.zip)")
        if not path:
            return

        self.close_zip()

        try:
            self.zf = zipfile.ZipFile(path, "r")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"ZIP을 열 수 없습니다.\n\n{e}")
            return

        self.zip_path = Path(path)
        self.zip_label.setText(f"ZIP: {self.zip_path}")
        self.load_entries()

    def close_zip(self):
        self.list_widget.clear()
        self.entries.clear()
        self.current_entry = None
        self.last_raw_bytes = None
        self.entry_label.setText("파일: -")
        self.text.clear()
        self.status.setText("")
        if self.zf is not None:
            try:
                self.zf.close()
            except Exception:
                pass
        self.zf = None
        self.zip_path = None

    def load_entries(self):
        assert self.zf is not None
        self.entries.clear()
        self.list_widget.clear()

        infos: list[EntryInfo] = []
        for zi in self.zf.infolist():
            if zi.is_dir():
                continue
            if is_text_candidate(zi.filename):
                infos.append(EntryInfo(name=zi.filename, size=zi.file_size))

        infos.sort(key=lambda x: x.name.lower())
        self.entries = infos

        for e in self.entries:
            self.list_widget.addItem(f"{e.name}  ({e.size:,} bytes)")

        self.status.setText(f"텍스트 후보 {len(self.entries)}개")
        if self.entries:
            self.list_widget.setCurrentRow(0)

    def apply_filter(self):
        q = self.filter_edit.text().strip().lower()
        self.list_widget.clear()
        for e in self.entries:
            if (not q) or (q in e.name.lower()):
                self.list_widget.addItem(f"{e.name}  ({e.size:,} bytes)")

    def _entry_by_display_row(self, row: int) -> EntryInfo | None:
        item = self.list_widget.item(row)
        if row < 0 or item is None:
            return None
        txt = item.text()
        name = txt.split("  (", 1)[0]
        for e in self.entries:
            if e.name == name:
                return e
        return None

    def on_select_entry(self):
        entry = self._entry_by_display_row(self.list_widget.currentRow())
        if entry is None or self.zf is None:
            return

        self.current_entry = entry
        self.user_overrode_wrap_for_current = False  # 새 파일 선택 시 override 초기화

        self.entry_label.setText(f"파일: {entry.name}  (원본 {entry.size:,} bytes)")
        self.read_and_show(entry)

        # ✅ 파일 선택 후 권장 줄바꿈 자동 적용
        self.apply_recommended_wrap_if_needed(entry.name)

    # --- 표시 ---
    def read_and_show(self, entry: EntryInfo):
        if self.zf is None:
            return

        try:
            with self.zf.open(entry.name, "r") as fp:
                raw = fp.read(PREVIEW_MAX_BYTES + 1)
        except Exception as e:
            self.text.setPlainText("")
            self.status.setText(f"읽기 실패: {e}")
            return

        truncated = len(raw) > PREVIEW_MAX_BYTES
        if truncated:
            raw = raw[:PREVIEW_MAX_BYTES]

        self.last_raw_bytes = raw
        text, used_enc, warning = self.decode_bytes(raw)

        self.text.setPlainText(text)

        msg = f"표시 인코딩: {used_enc}"
        if truncated:
            msg += f" | ⚠ 일부만 표시(최대 {PREVIEW_MAX_BYTES//1024//1024}MB)"
        if warning:
            msg += f" | {warning}"
        self.status.setText(msg)

        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.text.setTextCursor(cursor)

    # --- 인코딩 ---
    def decode_bytes(self, raw: bytes) -> tuple[str, str, str]:
        mode = self.encoding_combo.currentText()
        if mode == "UTF-8":
            return self._decode_with(raw, "utf-8")
        if mode == "CP949":
            return self._decode_with(raw, "cp949")
        return self._decode_try_auto(raw)

    def _decode_with(self, raw: bytes, enc: str) -> tuple[str, str, str]:
        try:
            return raw.decode(enc), enc, ""
        except UnicodeDecodeError:
            s = raw.decode(enc, errors="replace")
            return s, enc, "⚠ 디코딩 오류(일부 문자가 대체됨). 다른 인코딩을 선택해보세요."

    def _decode_try_auto(self, raw: bytes) -> tuple[str, str, str]:
        try:
            return raw.decode("utf-8"), "utf-8", ""
        except UnicodeDecodeError:
            try:
                return raw.decode("cp949"), "cp949", "자동 판별: UTF-8 실패 → CP949로 표시"
            except UnicodeDecodeError:
                s = raw.decode("utf-8", errors="replace")
                return s, "utf-8", "⚠ UTF-8/CP949 모두 완벽히 디코딩되지 않음(대체문자 포함)"

    def redecode_current(self):
        if self.last_raw_bytes is None:
            return
        text, used_enc, warning = self.decode_bytes(self.last_raw_bytes)
        self.text.setPlainText(text)

        msg = f"표시 인코딩: {used_enc}"
        if warning:
            msg += f" | {warning}"
        self.status.setText(msg)

    # --- 검색 ---
    def search_next(self, backward: bool = False):
        needle = self.search_edit.text()
        if not needle:
            return

        flags = QTextDocument.FindFlags()
        if backward:
            flags |= QTextDocument.FindBackward

        found = self.text.find(needle, flags)
        if not found:
            cursor = self.text.textCursor()
            cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            self.text.setTextCursor(cursor)
            found = self.text.find(needle, flags)

        if not found:
            self.status.setText(self.status.text() + " | 검색 결과 없음")


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
