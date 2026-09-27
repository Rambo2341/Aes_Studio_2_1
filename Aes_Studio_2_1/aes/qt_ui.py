from __future__ import annotations
"""Aes Studio desktop UI (PySide6 / Qt).

Layout: icon rail | page. Chat page = conversations sidebar | messages + composer | activity panel.
All agent work runs in background threads; events reach the UI through Qt signals, so the
window never freezes. Arabic/English UI with right-to-left layout for Arabic.
"""
import json, os, re, subprocess, sys, threading, time, webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QSize, QRectF
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPen, QShortcut, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QToolButton, QVBoxLayout, QWidget, QHeaderView,
)

from .paths import APP_VERSION, DATA, WORKSPACE, EXPORTS, IDENTITY_DATA, REPORTS, RESOURCE_ROOT, BUNDLE_ROOT
from .db import Database
from .model_runtime import RuntimeManager, RUNTIMES
from .security import PermissionManager
from .tools import ToolRegistry
from .agent import AgentEngine
from .knowledge import KnowledgeBase
from .hardware import is_cloud

ARABIC = re.compile(r'[؀-ۿ]')

# ---------------------------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------------------------
T = dict(bg='#070B12', rail='#05080D', side='#0A111B', card='#0E1724', card2='#132033', line='#1C2B40',
         text='#E8F1FB', muted='#8A9BB0', accent='#1E90FF', accent2='#22D3EE', good='#34D399', warn='#FBBF24',
         bad='#F87171', user='#12304F', input='#0A1320')

QSS = f"""
* {{ font-family: 'Segoe UI', 'Noto Sans Arabic', 'Noto Sans', sans-serif; font-size: 10pt; color: {T['text']}; }}
QMainWindow, QWidget#page {{ background: {T['bg']}; }}
QWidget#rail {{ background: {T['rail']}; border-right: 1px solid {T['line']}; }}
QWidget#side {{ background: {T['side']}; }}
QFrame#card {{ background: {T['card']}; border: 1px solid {T['line']}; border-radius: 12px; }}
QLabel#h1 {{ font-size: 18pt; font-weight: 600; }}
QLabel#h2 {{ font-size: 12pt; font-weight: 600; }}
QLabel#muted, QLabel#hint {{ color: {T['muted']}; }}
QLabel#big {{ font-size: 22pt; font-weight: 700; color: {T['accent2']}; }}
QToolButton#railbtn {{ background: transparent; border: none; border-radius: 10px; font-size: 16pt; color: {T['muted']}; padding: 6px; }}
QToolButton#railbtn:hover {{ background: {T['card']}; color: {T['text']}; }}
QToolButton#railbtn:checked {{ background: {T['card2']}; color: {T['accent2']}; }}
QPushButton {{ background: {T['card2']}; border: 1px solid {T['line']}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {T['accent']}; }}
QPushButton:disabled {{ color: {T['muted']}; }}
QPushButton#primary {{ background: {T['accent']}; border: none; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: #4AA8FF; }}
QPushButton#danger {{ background: #3A1620; border: 1px solid #5B2230; color: #FFB4BF; }}
QLineEdit, QPlainTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {T['input']}; border: 1px solid {T['line']}; border-radius: 8px; padding: 6px; selection-background-color: {T['accent']}; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {T['accent']}; }}
QComboBox QAbstractItemView {{ background: {T['card']}; border: 1px solid {T['line']}; selection-background-color: {T['card2']}; }}
QListWidget, QTableWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 8px; border-radius: 8px; margin: 1px 4px; }}
QListWidget::item:selected {{ background: {T['card2']}; }}
QListWidget::item:hover {{ background: {T['card']}; }}
QHeaderView::section {{ background: {T['card']}; border: none; padding: 6px; color: {T['muted']}; }}
QTableWidget {{ gridline-color: {T['line']}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 8px 12px; color: {T['muted']}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {T['text']}; border-bottom: 2px solid {T['accent2']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {T['line']}; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {T['line']}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QSplitter::handle {{ background: {T['line']}; }}
QFrame#bubble_user {{ background: {T['user']}; border-radius: 14px; }}
QFrame#bubble_ai {{ background: {T['card']}; border: 1px solid {T['line']}; border-radius: 14px; }}
QFrame#composer {{ background: {T['card']}; border: 1px solid {T['line']}; border-radius: 14px; }}
QStatusBar {{ background: {T['rail']}; color: {T['muted']}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
"""

# ---------------------------------------------------------------------------------------------
# Localisation
# ---------------------------------------------------------------------------------------------
STR = {
 'chat': ('Chat', 'المحادثة'), 'train': ('Training', 'التدريب'), 'library': ('Library', 'المكتبة'),
 'models': ('Brains', 'العقول'), 'tools': ('Permissions', 'الصلاحيات'), 'settings': ('Settings', 'الإعدادات'),
 'new_chat': ('+  New chat', '+  محادثة جديدة'), 'search': ('Search chats…', 'ابحث في المحادثات…'),
 'type_here': ('Message Aes…  (Ctrl+Enter to send)', 'اكتب لـ Aes…  (Ctrl+Enter للإرسال)'),
 'send': ('Send', 'إرسال'), 'stop': ('Stop', 'إيقاف'), 'activity': ('Activity', 'النشاط'), 'sources': ('Sources', 'المصادر'),
 'memory': ('Memory', 'الذاكرة'), 'knowledge': ('Knowledge', 'المعرفة'), 'goals': ('Goals', 'الأهداف'),
 'mode_agent': ('Agent', 'وكيل'), 'mode_code': ('Code + Review', 'كود + مراجعة'), 'mode_plan': ('Plan', 'خطة'), 'mode_research': ('Research', 'بحث'),
 'trust_ask': ('Ask', 'اسأل'), 'trust_auto': ('Auto', 'تلقائي'), 'trust_full': ('Full access', 'صلاحية كاملة'),
 'welcome': ('Hi ABD — what should we build today?', 'هلا ABD — وش نسوي اليوم؟'),
 'welcome_sub': ('Aes runs on your own PC. Local brain = free and private.', 'Aes شغّال على جهازك. العقل المحلي = مجاني وخاص.'),
 'working': ('Aes is working…', 'Aes يشتغل…'), 'idle': ('Ready', 'جاهز'), 'stopped': ('Stopped', 'توقف'),
 'train_title': ('Training Center', 'مركز التدريب'),
 'train_sub': ('Aes studies, practises and tests itself. Only computer-verified answers become training data.',
               'Aes يدرس ويتمرن ويختبر نفسه. ما يدخل التدريب إلا الأجوبة اللي تحقق منها الكمبيوتر.'),
 'daily': ('Daily training', 'التدريب اليومي'), 'hours': ('Hours', 'الساعات'), 'start_training': ('Start training now', 'ابدأ التدريب الآن'),
 'schedule': ('Every night at', 'كل ليلة الساعة'), 'install_schedule': ('Install schedule', 'ثبّت الجدول'),
 'research_mode': ('Research Mode', 'وضع البحث'), 'research_hint': ('e.g. Master Blender: modelling, rigging, animation', 'مثال: احترف Blender: مودلنج، ريغ، أنميشن'),
 'start_research': ('Start research', 'ابدأ البحث'), 'show_browser': ('Show Chrome while reading', 'افتح كروم وأنا أشوف'),
 'curriculum': ('Curriculum', 'المنهج'), 'queue_units': ('Queue next lessons', 'أضف الدروس الجاية'),
 'brain_growth': ('Brain growth (LoRA)', 'نمو العقل (LoRA)'), 'auto_train_brain': ('Train the brain automatically when enough data', 'درّب العقل تلقائياً لما تكفي البيانات'),
 'base_model': ('Base model', 'الموديل الأساسي'), 'min_examples': ('Min. new examples', 'أقل عدد أمثلة جديدة'),
 'progress': ('Progress (last 14 days)', 'التقدم (آخر 14 يوم)'), 'log': ('Live log', 'السجل المباشر'), 'reports': ('Open reports', 'افتح التقارير'),
 'examples': ('Training examples', 'أمثلة التدريب'), 'memories': ('Memories', 'الذكريات'), 'docs': ('Documents', 'المستندات'),
 'maths': ('Maths', 'رياضيات'), 'code': ('Code', 'برمجة'),
 'import_files': ('Import files…', 'استورد ملفات…'), 'import_folder': ('Import folder…', 'استورد مجلد…'),
 'add': ('Add', 'أضف'), 'delete': ('Delete', 'حذف'), 'save': ('Save', 'حفظ'), 'test': ('Test', 'اختبر'), 'set_default': ('Set default', 'اجعله الافتراضي'),
 'hardware': ('This PC', 'جهازك'), 'local_free': ('local · free', 'محلي · مجاني'), 'cloud_paid': ('cloud · paid', 'سحابي · مدفوع'),
 'language': ('Language', 'اللغة'), 'identity': ('Identity files', 'ملفات الهوية'), 'data_folder': ('Data folder', 'مجلد البيانات'),
 'owner_api': ('Owner API token', 'مفتاح API الخاص فيك'), 'copy': ('Copy', 'نسخ'), 'regenerate': ('Regenerate', 'جدّد'),
 'max_steps': ('Max agent steps', 'أقصى خطوات للوكيل'), 'restart_lang': ('Language changes apply now.', 'تم تغيير اللغة.'),
 'perm_title': ('Aes wants to act', 'Aes يبي ينفّذ'), 'allow': ('Allow', 'اسمح'), 'deny': ('Deny', 'ارفض'),
 'busy': ('Aes is busy with another task. Press Stop first.', 'Aes مشغول بمهمة ثانية. اضغط إيقاف أول.'),
 'no_chat': ('No messages yet', 'ما في رسائل'), 'pin': ('Pin', 'تثبيت'), 'unpin': ('Unpin', 'إلغاء التثبيت'), 'rename': ('Rename', 'إعادة تسمية'),
 'export': ('Export as Markdown', 'تصدير Markdown'), 'project': ('Project', 'المشروع'), 'no_project': ('No project', 'بدون مشروع'),
 'doctor': ('Run check', 'افحص'), 'policy': ('Policy', 'السياسة'), 'risk': ('Risk', 'الخطورة'), 'tool': ('Tool', 'الأداة'),
}


class I18N:
    lang = 'en'

    @classmethod
    def t(cls, key):
        en, ar = STR.get(key, (key, key))
        return ar if cls.lang == 'ar' else en


def tr(key): return I18N.t(key)


def rtl(text): return bool(ARABIC.search(text or ''))


# ---------------------------------------------------------------------------------------------
# Thread bridge
# ---------------------------------------------------------------------------------------------
class Bridge(QObject):
    agent_event = Signal(dict)
    ask = Signal(object)
    task_done = Signal(str, object, object)   # kind, result, error
    text_ready = Signal(str, str)              # target, text (background helpers)
    log = Signal(str)


def card(parent=None):
    f = QFrame(parent); f.setObjectName('card'); return f


def label(text, name=None, wrap=False):
    l = QLabel(text)
    if name: l.setObjectName(name)
    l.setWordWrap(wrap); return l


# ---------------------------------------------------------------------------------------------
# Chat widgets
# ---------------------------------------------------------------------------------------------
class Bubble(QFrame):
    def __init__(self, role, text, meta=None):
        super().__init__()
        self.setObjectName('bubble_user' if role == 'user' else 'bubble_ai')
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(6)
        head = QHBoxLayout()
        who = label('ABD' if role == 'user' else 'Aes', 'h2'); head.addWidget(who); head.addStretch(1)
        if meta and meta.get('tool_traces'):
            head.addWidget(label(f"⚙ {len(meta['tool_traces'])}", 'muted'))
        copy = QToolButton(); copy.setText('⧉'); copy.setToolTip(tr('copy')); copy.setAutoRaise(True)
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.body.text()))
        head.addWidget(copy); lay.addLayout(head)
        self.body = QLabel(); self.body.setWordWrap(True); self.body.setTextFormat(Qt.MarkdownText)
        self.body.setTextInteractionFlags(Qt.TextBrowserInteraction); self.body.setOpenExternalLinks(True)
        lay.addWidget(self.body); self.set_text(text)

    def set_text(self, text):
        text = text or ''
        shown = re.sub(r'<tool_calls?>.*?(</tool_calls?>|$)', '', text, flags=re.S).strip()
        self.body.setText(shown if shown else '…')
        d = Qt.RightToLeft if rtl(shown) else Qt.LeftToRight
        self.body.setLayoutDirection(d)
        # AlignAbsolute: Arabic text sits on the right and English on the left, whatever the UI language.
        self.body.setAlignment((Qt.AlignRight if d == Qt.RightToLeft else Qt.AlignLeft) | Qt.AlignAbsolute | Qt.AlignTop)


class ChatView(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.inner = QWidget(); self.inner.setObjectName('page')
        self.lay = QVBoxLayout(self.inner); self.lay.setContentsMargins(24, 18, 24, 18); self.lay.setSpacing(12)
        self.lay.addStretch(1); self.setWidget(self.inner); self.live = None

    def clear(self):
        while self.lay.count() > 1:
            w = self.lay.takeAt(0).widget()
            if w: w.hide(); w.setParent(None); w.deleteLater()
        self.live = None

    def add(self, role, text, meta=None):
        b = Bubble(role, text, meta)
        row = QHBoxLayout(); wrap = QWidget(); wrap.setLayout(row); row.setContentsMargins(0, 0, 0, 0)
        if role == 'user':
            row.addStretch(1); row.addWidget(b, 5)
        else:
            row.addWidget(b, 8); row.addStretch(1)
        self.lay.insertWidget(self.lay.count() - 1, wrap)
        QTimer.singleShot(30, lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()))
        return b

    def welcome(self):
        box = QWidget(); v = QVBoxLayout(box); v.setAlignment(Qt.AlignCenter)
        logo = RESOURCE_ROOT / 'assets' / 'aes.png'
        if logo.exists():
            l = QLabel(); l.setPixmap(QIcon(str(logo)).pixmap(72, 72)); l.setAlignment(Qt.AlignCenter); v.addWidget(l)
        t = label(tr('welcome'), 'h1'); t.setAlignment(Qt.AlignCenter); v.addWidget(t)
        s = label(tr('welcome_sub'), 'muted'); s.setAlignment(Qt.AlignCenter); v.addWidget(s)
        self.lay.insertWidget(self.lay.count() - 1, box)


class ProgressChart(QWidget):
    """Bars for maths % and code % per day (from daily_history)."""
    def __init__(self):
        super().__init__(); self.data = []; self.setMinimumHeight(170)

    def set_data(self, history):
        self.data = history[-14:]; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height(); pad = 28
        p.setPen(QPen(QColor(T['line']), 1))
        for i in range(5):
            y = pad + (h - 2 * pad) * i / 4; p.drawLine(pad, int(y), w - 8, int(y))
        if not self.data:
            p.setPen(QColor(T['muted'])); p.drawText(self.rect(), Qt.AlignCenter, '—'); return
        n = len(self.data); slot = (w - pad - 8) / n; bw = max(4, slot * 0.32)
        pct = lambda a: (a[0] / a[1]) if a and a[1] else 0
        for i, d in enumerate(self.data):
            x = pad + i * slot + slot * 0.15
            for j, (key, col) in enumerate((('math', T['accent']), ('code', T['accent2']))):
                v = pct(d.get(key)); bh = (h - 2 * pad) * v
                p.fillRect(QRectF(x + j * (bw + 2), h - pad - bh, bw, bh), QColor(col))
            p.setPen(QColor(T['muted'])); p.drawText(int(x), h - 8, d.get('date', '')[5:])
        p.setPen(QColor(T['muted'])); p.drawText(pad, 14, f"■ {tr('maths')}   ■ {tr('code')}   (0–100%)")


# ---------------------------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------------------------
class AesWindow(QMainWindow):
    PAGES = ['chat', 'train', 'library', 'models', 'tools', 'settings']
    ICONS = {'chat': '✦', 'train': '☾', 'library': '⌁', 'models': '◈', 'tools': '⌘', 'settings': '⚙'}

    def __init__(self, db_path, core=None):
        super().__init__()
        self.bridge = Bridge()
        if core:
            self.db, self.runtimes, self.tools, self.agent = core
        else:
            self.db = Database(db_path); self.runtimes = RuntimeManager()
            perm = PermissionManager(self.db, self._ask_permission)
            self.tools = ToolRegistry(WORKSPACE, self.db, perm)
            self.agent = AgentEngine(self.db, self.runtimes, self.tools)
        self.agent.listeners.append(self.bridge.agent_event.emit)
        self.bridge.agent_event.connect(self._on_agent_event)
        self.bridge.ask.connect(self._on_ask)
        self.bridge.task_done.connect(self._on_task_done)
        self.bridge.log.connect(self._on_log)
        self.bridge.text_ready.connect(lambda target, text: getattr(self, target).setPlainText(text))
        self.cid = None; self.busy = None; self.started = 0.0; self.live_text = ''
        lang = self.db.setting('ui_language', 'auto')
        I18N.lang = 'ar' if lang == 'ar' else 'en'
        self.setWindowTitle(f'Aes Studio {APP_VERSION}')
        icon = RESOURCE_ROOT / 'assets' / 'aes.ico'
        if icon.exists(): self.setWindowIcon(QIcon(str(icon)))
        self.resize(1440, 900); self.setMinimumSize(1100, 700)
        self._build()
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(500)

    # ---------------- layout ----------------
    def _build(self):
        QApplication.instance().setLayoutDirection(Qt.RightToLeft if I18N.lang == 'ar' else Qt.LeftToRight)
        root = QWidget(); root.setObjectName('page'); h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        rail = QWidget(); rail.setObjectName('rail'); rail.setFixedWidth(64); rv = QVBoxLayout(rail); rv.setContentsMargins(8, 12, 8, 12); rv.setSpacing(6)
        logo = RESOURCE_ROOT / 'assets' / 'aes.png'
        if logo.exists():
            l = QLabel(); l.setPixmap(QIcon(str(logo)).pixmap(34, 34)); l.setAlignment(Qt.AlignCenter); rv.addWidget(l); rv.addSpacing(10)
        self.stack = QStackedWidget(); self.rail_btns = {}
        builders = {'chat': self._page_chat, 'train': self._page_train, 'library': self._page_library,
                    'models': self._page_models, 'tools': self._page_tools, 'settings': self._page_settings}
        for key in self.PAGES:
            b = QToolButton(); b.setObjectName('railbtn'); b.setText(self.ICONS[key]); b.setToolTip(tr(key)); b.setCheckable(True)
            b.setFixedSize(46, 46); b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            if key == 'settings': rv.addStretch(1)
            rv.addWidget(b); self.rail_btns[key] = b
            page = builders[key](); page.setObjectName('page'); self.stack.addWidget(page)
        h.addWidget(rail); h.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.state_lbl = QLabel(); self.model_lbl = QLabel(); self.trust_lbl = QLabel()
        sb = self.statusBar(); sb.addWidget(self.state_lbl, 1); sb.addPermanentWidget(self.model_lbl); sb.addPermanentWidget(self.trust_lbl)
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.send)
        QShortcut(QKeySequence('Ctrl+N'), self, activated=self.new_chat)
        QShortcut(QKeySequence('Escape'), self, activated=self.stop)
        self.show_page('chat'); self.refresh_all()

    def show_page(self, key):
        for k, b in self.rail_btns.items(): b.setChecked(k == key)
        self.stack.setCurrentIndex(self.PAGES.index(key))
        getattr(self, f'refresh_{key}', lambda: None)()

    def refresh_all(self):
        for k in self.PAGES:
            try: getattr(self, f'refresh_{k}', lambda: None)()
            except Exception: pass
        self._update_status()

    # ---------------- chat page ----------------
    def _page_chat(self):
        page = QWidget(); outer = QHBoxLayout(page); outer.setContentsMargins(0, 0, 0, 0)
        split = QSplitter(Qt.Horizontal); outer.addWidget(split)
        # sidebar
        side = QWidget(); side.setObjectName('side'); sv = QVBoxLayout(side); sv.setContentsMargins(10, 12, 10, 10)
        nb = QPushButton(tr('new_chat')); nb.setObjectName('primary'); nb.clicked.connect(self.new_chat); sv.addWidget(nb)
        self.chat_search = QLineEdit(); self.chat_search.setPlaceholderText(tr('search')); self.chat_search.textChanged.connect(self.refresh_chat_list); sv.addWidget(self.chat_search)
        self.chat_list = QListWidget(); self.chat_list.itemClicked.connect(self._open_chat_item)
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu); self.chat_list.customContextMenuRequested.connect(self._chat_menu)
        sv.addWidget(self.chat_list, 1)
        self.project_box = QComboBox(); sv.addWidget(label(tr('project'), 'muted')); sv.addWidget(self.project_box)
        split.addWidget(side)
        # centre
        centre = QWidget(); cv = QVBoxLayout(centre); cv.setContentsMargins(0, 0, 0, 12); cv.setSpacing(8)
        self.chat_title = label('', 'h2'); self.chat_title.setContentsMargins(24, 12, 24, 0); cv.addWidget(self.chat_title)
        self.view = ChatView(); cv.addWidget(self.view, 1)
        comp = QFrame(); comp.setObjectName('composer'); comp_l = QVBoxLayout(comp); comp_l.setContentsMargins(12, 10, 12, 10)
        self.prompt = QPlainTextEdit(); self.prompt.setPlaceholderText(tr('type_here')); self.prompt.setFixedHeight(90)
        self.prompt.setStyleSheet('border:none;background:transparent;')
        comp_l.addWidget(self.prompt)
        bar = QHBoxLayout()
        self.mode_box = QComboBox(); [self.mode_box.addItem(tr(k), k) for k in ('mode_agent', 'mode_code', 'mode_plan', 'mode_research')]
        self.model_box = QComboBox(); self.model_box.currentIndexChanged.connect(self._model_changed)
        self.trust_box = QComboBox()
        for k, v in (('trust_ask', 'ask'), ('trust_auto', 'auto'), ('trust_full', 'full')): self.trust_box.addItem(tr(k), v)
        self.trust_box.currentIndexChanged.connect(self._trust_changed)
        for w in (self.mode_box, self.model_box, self.trust_box): bar.addWidget(w)
        bar.addStretch(1)
        self.send_btn = QPushButton(tr('send')); self.send_btn.setObjectName('primary'); self.send_btn.clicked.connect(self.send_or_stop); bar.addWidget(self.send_btn)
        comp_l.addLayout(bar)
        wrap = QHBoxLayout(); wrap.setContentsMargins(24, 0, 24, 0); wrap.addWidget(comp); cv.addLayout(wrap)
        split.addWidget(centre)
        # right panel
        right = QWidget(); right.setObjectName('side'); rv = QVBoxLayout(right); rv.setContentsMargins(8, 10, 8, 8)
        self.right_tabs = QTabWidget()
        self.activity = QListWidget(); self.activity.setWordWrap(True); self.activity.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.right_tabs.addTab(self.activity, tr('activity'))
        self.sources = QListWidget(); self.sources.itemDoubleClicked.connect(lambda it: webbrowser.open(it.text()))
        self.right_tabs.addTab(self.sources, tr('sources'))
        self.sources.setWordWrap(True); self.sources.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.goal_mini = QListWidget(); self.goal_mini.setWordWrap(True); self.right_tabs.addTab(self.goal_mini, tr('goals'))
        rv.addWidget(self.right_tabs)
        split.addWidget(right)
        split.setSizes([260, 860, 320]); split.setStretchFactor(1, 1)
        return page

    def refresh_chat(self):
        self.refresh_chat_list(); self._fill_models(); self._fill_projects()
        i = self.trust_box.findData(self.db.setting('permission_mode', 'ask')); self.trust_box.blockSignals(True); self.trust_box.setCurrentIndex(max(0, i)); self.trust_box.blockSignals(False)
        if not self.cid: self.view.clear(); self.view.welcome(); self.chat_title.setText('')
        self.goal_mini.clear()
        for g in self.db.goals()[:40]: self.goal_mini.addItem(f"[{g['status']}] {g['title']}")

    def refresh_chat_list(self):
        self.chat_list.clear()
        for c in self.db.conversations(self.chat_search.text().strip() if hasattr(self, 'chat_search') else ''):
            pinned = ('pinned' in c.keys() and c['pinned'])
            it = QListWidgetItem(('📌 ' if pinned else '') + (c['title'] or 'Chat')); it.setData(Qt.UserRole, c['id'])
            if rtl(c['title']): it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.chat_list.addItem(it)
            if c['id'] == self.cid: it.setSelected(True)

    def _fill_models(self):
        cur = self.db.setting('default_model', 'Aes Local'); self.model_box.blockSignals(True); self.model_box.clear()
        for r in self.db.models():
            tag = '☁ ' if is_cloud(r) else '● '
            self.model_box.addItem(tag + r['name'], r['name'])
        i = self.model_box.findData(cur); self.model_box.setCurrentIndex(max(0, i)); self.model_box.blockSignals(False)

    def _fill_projects(self):
        self.project_box.blockSignals(True); self.project_box.clear(); self.project_box.addItem(tr('no_project'), None)
        for p in self.db.projects(): self.project_box.addItem(p['name'], p['id'])
        self.project_box.blockSignals(False)

    def _model_changed(self, _):
        name = self.model_box.currentData()
        if name: self.db.set_setting('default_model', name); self._update_status()

    def _trust_changed(self, _):
        self.db.set_setting('permission_mode', self.trust_box.currentData()); self._update_status()

    def new_chat(self):
        self.cid = None; self.view.clear(); self.view.welcome(); self.chat_title.setText(''); self.activity.clear(); self.sources.clear()
        self.show_page('chat'); self.prompt.setFocus()

    def _open_chat_item(self, it):
        self.open_chat(it.data(Qt.UserRole))

    def open_chat(self, cid):
        self.cid = cid; self.view.clear(); self.sources.clear()
        c = self.db.one('SELECT * FROM conversations WHERE id=?', (cid,)); self.chat_title.setText(c['title'] if c else '')
        urls = []
        for m in self.db.messages(cid):
            meta = json.loads(m['meta_json'] or '{}')
            if m['role'] in ('user', 'assistant'): self.view.add(m['role'], m['content'], meta)
            for t in meta.get('tool_traces', []):
                urls += re.findall(r'https?://[^\s\'"<>)\]]+', json.dumps(t.get('arguments', {})) + ' ' + str(t.get('result', ''))[:3000])
        for u in list(dict.fromkeys(urls))[:200]: self.sources.addItem(u)
        if not self.db.messages(cid): self.view.welcome()

    def _chat_menu(self, pos):
        it = self.chat_list.itemAt(pos)
        if not it: return
        cid = it.data(Qt.UserRole); c = self.db.one('SELECT * FROM conversations WHERE id=?', (cid,))
        m = QMenu(self)
        pin = m.addAction(tr('unpin') if c and c['pinned'] else tr('pin'))
        ren = m.addAction(tr('rename')); exp = m.addAction(tr('export')); dele = m.addAction(tr('delete'))
        a = m.exec(self.chat_list.mapToGlobal(pos))
        if a == pin: self.db.set_pinned(cid, not (c and c['pinned']))
        elif a == ren:
            t, ok = QInputDialog.getText(self, tr('rename'), tr('rename'), text=c['title'] if c else '')
            if ok and t.strip(): self.db.rename_conversation(cid, t.strip())
        elif a == exp:
            p, _ = QFileDialog.getSaveFileName(self, tr('export'), str(Path.home() / f'aes_chat_{cid[:8]}.md'), 'Markdown (*.md)')
            if p: Path(p).write_text(self.db.export_conversation(cid), encoding='utf-8')
        elif a == dele:
            if QMessageBox.question(self, tr('delete'), tr('delete') + '?') == QMessageBox.Yes:
                self.db.delete_conversation(cid)
                if cid == self.cid: self.new_chat()
        self.refresh_chat_list()

    # ---------------- sending / agent events ----------------
    def send_or_stop(self):
        if self.busy: self.stop()
        else: self.send()

    def send(self):
        text = self.prompt.toPlainText().strip()
        if not text: return
        if self.busy: QMessageBox.information(self, 'Aes', tr('busy')); return
        model = self.model_box.currentData() or self.db.setting('default_model', 'Aes Local')
        if not self.cid:
            self.view.clear(); self.cid = self.db.new_conversation(text[:60], self.project_box.currentData(), model)
        self.prompt.clear(); self.view.add('user', text); self.activity.clear()
        self.live_text = ''; self.view.live = self.view.add('assistant', '…')
        mode = self.mode_box.currentData(); pid = self.project_box.currentData(); cid = self.cid

        def work():
            if mode == 'mode_code': return self.agent.coordinated_code(cid, model, text, pid)
            return self.agent.run(cid, model, text, {'mode_plan': 'plan', 'mode_research': 'research'}.get(mode, 'agent'), pid)
        self._start('chat', work)

    def stop(self):
        if self.busy:
            self.agent.cancel(); self.db.set_setting('autopilot_stop', '1')
            self.state_lbl.setText('⏹ ' + tr('stopped'))

    def _start(self, kind, fn):
        self.busy = kind; self.started = time.time(); self.send_btn.setText('⏹ ' + tr('stop')); self.send_btn.setObjectName('danger')
        self.send_btn.style().unpolish(self.send_btn); self.send_btn.style().polish(self.send_btn)
        self.db.set_setting('autopilot_stop', '0')

        def run():
            try: res, err = fn(), None
            except Exception as e: res, err = None, e
            self.bridge.task_done.emit(kind, res, err)
        threading.Thread(target=run, daemon=True).start()

    def _on_task_done(self, kind, res, err):
        self.busy = None; self.send_btn.setText(tr('send')); self.send_btn.setObjectName('primary')
        self.send_btn.style().unpolish(self.send_btn); self.send_btn.style().polish(self.send_btn)
        if kind in ('doctor', 'model test'):
            self.hw_view.setPlainText(str(err) if err else str(res))
        elif kind == 'library':
            self.refresh_library()
        if kind == 'chat':
            if err:
                if self.view.live: self.view.live.set_text(f'⚠️ {err}')
            elif self.cid:
                self.open_chat(self.cid)
            self.refresh_chat_list()
        elif kind not in ('doctor', 'model test'):
            self._on_log(f'✔ {kind} finished' + (f': {res}' if res and not err else '') + (f'  ERROR: {err}' if err else ''))
            self.refresh_train()
        self._update_status()

    def _on_agent_event(self, ev):
        t = ev.get('type')
        if t == 'token' and self.view.live is not None and self.busy == 'chat':
            self.live_text += ev.get('text', ''); self.view.live.set_text(self.live_text)
        elif t == 'model_start':
            self.live_text = ''
            self.activity.addItem(f"🧠 step {ev.get('step')} · {ev.get('model')}")
        elif t == 'tool_start':
            args = ', '.join(f'{k}={v}' for k, v in ev.get('arguments', {}).items())[:160]
            it = QListWidgetItem(f"⏳ {ev['tool']}  {args}"); it.setData(Qt.UserRole, ev.get('call_id')); self.activity.addItem(it)
        elif t == 'tool_end':
            for i in range(self.activity.count() - 1, -1, -1):
                it = self.activity.item(i)
                if it.data(Qt.UserRole) == ev.get('call_id'):
                    icon = '✅' if ev.get('status') == 'ok' else '❌'
                    it.setText(it.text().replace('⏳', icon, 1) + f"   {ev.get('seconds')}s"); it.setToolTip(ev.get('result', '')[:2000]); break
            for u in re.findall(r'https?://[^\s\'"<>)\]]+', ev.get('result', '')): self.sources.addItem(u)
        elif t == 'cancelled':
            self.activity.addItem('⏹ ' + tr('stopped'))
        self.activity.scrollToBottom()

    def _ask_permission(self, req):
        if threading.current_thread() is threading.main_thread():
            return self._permission_dialog(req)
        holder = {'ev': threading.Event(), 'ok': False}
        self.bridge.ask.emit((req, holder)); holder['ev'].wait(); return holder['ok']

    def _on_ask(self, payload):
        req, holder = payload; holder['ok'] = self._permission_dialog(req); holder['ev'].set()

    def _permission_dialog(self, req):
        box = QMessageBox(self); box.setWindowTitle(tr('perm_title')); box.setIcon(QMessageBox.Question)
        box.setText(f'<b>{req.tool_name}</b> · {tr("risk")}: {req.risk}'); box.setInformativeText(req.summary[:600])
        allow = box.addButton(tr('allow'), QMessageBox.AcceptRole); box.addButton(tr('deny'), QMessageBox.RejectRole)
        box.exec(); return box.clickedButton() == allow

    def _tick(self):
        if self.busy:
            self.state_lbl.setText(f"● {tr('working')}  {int(time.time() - self.started)}s  ·  {self.busy}")

    def _update_status(self):
        name = self.db.setting('default_model', ''); m = self.db.model(name)
        kind = tr('cloud_paid') if (m and is_cloud(m)) else tr('local_free')
        self.model_lbl.setText(f'  🧠 {name} ({kind})  ')
        mode = self.db.setting('permission_mode', 'ask')
        colour = {'ask': T['good'], 'auto': T['warn'], 'full': T['bad']}.get(mode, T['muted'])
        self.trust_lbl.setText(f"  <span style='color:{colour}'>● {tr('trust_' + mode)}</span>  "); self.trust_lbl.setTextFormat(Qt.RichText)
        if not self.busy: self.state_lbl.setText('● ' + tr('idle'))

    # ---------------- training page ----------------
    def _page_train(self):
        page = QWidget(); sc = QScrollArea(); sc.setWidgetResizable(True); inner = QWidget(); inner.setObjectName('page'); sc.setWidget(inner)
        outer = QVBoxLayout(page); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(sc)
        v = QVBoxLayout(inner); v.setContentsMargins(28, 22, 28, 22); v.setSpacing(14)
        v.addWidget(label(tr('train_title'), 'h1')); v.addWidget(label(tr('train_sub'), 'muted', True))
        # stats row
        stats = QHBoxLayout(); self.stat_lbls = {}
        for key in ('maths', 'code', 'examples', 'memories', 'docs'):
            c = card(); cl = QVBoxLayout(c); cl.addWidget(label(tr(key), 'muted')); val = label('—', 'big'); cl.addWidget(val)
            self.stat_lbls[key] = val; stats.addWidget(c)
        v.addLayout(stats)
        grid = QGridLayout(); grid.setSpacing(14)
        # daily
        c = card(); f = QVBoxLayout(c); f.addWidget(label(tr('daily'), 'h2'))
        row = QHBoxLayout(); row.addWidget(label(tr('hours')))
        self.hours = QDoubleSpinBox(); self.hours.setRange(0.25, 24); self.hours.setSingleStep(0.5); self.hours.setValue(float(self.db.setting('daily_hours', '3') or 3))
        row.addWidget(self.hours); row.addStretch(1); f.addLayout(row)
        b = QPushButton('▶  ' + tr('start_training')); b.setObjectName('primary'); b.clicked.connect(self.start_daily); f.addWidget(b)
        row = QHBoxLayout(); row.addWidget(label(tr('schedule')))
        self.sched_time = QLineEdit(self.db.setting('daily_time', '02:00')); self.sched_time.setFixedWidth(70); row.addWidget(self.sched_time)
        sb = QPushButton(tr('install_schedule')); sb.clicked.connect(self.install_schedule); row.addWidget(sb); row.addStretch(1); f.addLayout(row)
        grid.addWidget(c, 0, 0)
        # research
        c = card(); f = QVBoxLayout(c); f.addWidget(label(tr('research_mode'), 'h2'))
        self.research_prompt = QLineEdit(); self.research_prompt.setPlaceholderText(tr('research_hint')); f.addWidget(self.research_prompt)
        row = QHBoxLayout(); row.addWidget(label(tr('hours')))
        self.research_hours = QDoubleSpinBox(); self.research_hours.setRange(0.25, 24); self.research_hours.setValue(2); row.addWidget(self.research_hours)
        self.show_browser = QCheckBox(tr('show_browser')); row.addWidget(self.show_browser); row.addStretch(1); f.addLayout(row)
        b = QPushButton('🔎  ' + tr('start_research')); b.setObjectName('primary'); b.clicked.connect(self.start_research); f.addWidget(b)
        grid.addWidget(c, 0, 1)
        # curriculum
        c = card(); f = QVBoxLayout(c); f.addWidget(label(tr('curriculum'), 'h2'))
        self.track_boxes = {}
        tw = QWidget(); tg = QGridLayout(tw); tg.setContentsMargins(0, 0, 0, 0)
        try:
            from .curriculum import tracks
            for i, t in enumerate(tracks()):
                cb = QCheckBox(t); cb.setChecked(True); tg.addWidget(cb, i // 3, i % 3); self.track_boxes[t] = cb
        except Exception as e:
            tg.addWidget(label(str(e), 'muted'))
        f.addWidget(tw)
        b = QPushButton(tr('queue_units')); b.clicked.connect(self.queue_curriculum); f.addWidget(b)
        grid.addWidget(c, 1, 0)
        # brain growth
        c = card(); f = QFormLayout(c); f.addRow(label(tr('brain_growth'), 'h2'))
        self.lora_on = QCheckBox(tr('auto_train_brain')); self.lora_on.setChecked(self.db.setting('daily_lora_enabled', '0') == '1'); f.addRow(self.lora_on)
        self.lora_base = QLineEdit(self.db.setting('daily_lora_base', '')); f.addRow(tr('base_model'), self.lora_base)
        self.lora_min = QSpinBox(); self.lora_min.setRange(50, 100000); self.lora_min.setValue(int(self.db.setting('daily_lora_min_examples', '300') or 300)); f.addRow(tr('min_examples'), self.lora_min)
        b = QPushButton(tr('save')); b.clicked.connect(self.save_brain_settings); f.addRow(b)
        grid.addWidget(c, 1, 1)
        v.addLayout(grid)
        c = card(); f = QVBoxLayout(c); f.addWidget(label(tr('progress'), 'h2')); self.chart = ProgressChart(); f.addWidget(self.chart); v.addWidget(c)
        c = card(); f = QVBoxLayout(c)
        row = QHBoxLayout(); row.addWidget(label(tr('log'), 'h2')); row.addStretch(1)
        rb = QPushButton(tr('reports')); rb.clicked.connect(lambda: self.open_path(REPORTS)); row.addWidget(rb)
        st = QPushButton('⏹ ' + tr('stop')); st.setObjectName('danger'); st.clicked.connect(self.stop); row.addWidget(st); f.addLayout(row)
        self.train_log = QPlainTextEdit(); self.train_log.setReadOnly(True); self.train_log.setMinimumHeight(160); f.addWidget(self.train_log)
        v.addWidget(c)
        return page

    def refresh_train(self):
        if not hasattr(self, 'stat_lbls'): return
        hist = json.loads(self.db.setting('daily_history', '[]') or '[]')
        last = hist[-1] if hist else None
        pct = lambda a: f'{100 * a[0] / a[1]:.0f}%' if a and a[1] else '—'
        self.stat_lbls['maths'].setText(pct(last['math']) if last else '—')
        self.stat_lbls['code'].setText(pct(last['code']) if last else '—')
        self.stat_lbls['examples'].setText(str(len(self.db.training_examples())))
        self.stat_lbls['memories'].setText(str(len(self.db.memories())))
        self.stat_lbls['docs'].setText(str(len(self.db.docs())))
        self.chart.set_data(hist)

    def _on_log(self, line):
        if hasattr(self, 'train_log'):
            self.train_log.appendPlainText(time.strftime('%H:%M:%S  ') + str(line))

    def start_daily(self):
        if self.busy: QMessageBox.information(self, 'Aes', tr('busy')); return
        self.db.set_setting('daily_hours', str(self.hours.value()))
        from .daily import DailyTrainer
        model = self.db.setting('default_model', 'Aes Local'); hours = self.hours.value()
        self._on_log(f'▶ Daily training for {hours}h with {model}')
        self._start('training', lambda: DailyTrainer(self.db, self.agent, log=self.bridge.log.emit).run(model, hours=hours))

    def start_research(self):
        goal = self.research_prompt.text().strip()
        if not goal: return
        if self.busy: QMessageBox.information(self, 'Aes', tr('busy')); return
        from .research import ResearchMode
        self.db.set_setting('research_show_browser', '1' if self.show_browser.isChecked() else '0')
        model = self.db.setting('default_model', 'Aes Local'); hours = self.research_hours.value()
        self._on_log(f'🔎 Research "{goal}" for {hours}h')
        self._start('research', lambda: ResearchMode(self.db, self.agent, log=self.bridge.log.emit).run(model, goal, hours))

    def queue_curriculum(self):
        from .curriculum import queue
        picked = ','.join(t for t, cb in self.track_boxes.items() if cb.isChecked()) or 'all'
        n = queue(self.db, picked); self._on_log(f'Queued {n} curriculum goal(s): {picked}'); self.refresh_chat()

    def save_brain_settings(self):
        self.db.set_setting('daily_lora_enabled', '1' if self.lora_on.isChecked() else '0')
        self.db.set_setting('daily_lora_base', self.lora_base.text().strip())
        self.db.set_setting('daily_lora_min_examples', str(self.lora_min.value())); self._on_log('Brain growth settings saved.')

    def install_schedule(self):
        t = self.sched_time.text().strip() or '02:00'; self.db.set_setting('daily_time', t)
        bat = BUNDLE_ROOT / 'install_daily_task.bat'
        if os.name != 'nt' or not bat.exists():
            QMessageBox.information(self, 'Aes', f'Windows only: run install_daily_task.bat {t}'); return
        r = subprocess.run(['cmd', '/c', str(bat), t], capture_output=True, text=True)
        self._on_log((r.stdout or '') + (r.stderr or ''))

    # ---------------- library page ----------------
    def _page_library(self):
        page = QWidget(); v = QVBoxLayout(page); v.setContentsMargins(28, 22, 28, 22)
        v.addWidget(label(tr('library'), 'h1')); tabs = QTabWidget(); v.addWidget(tabs, 1)
        # knowledge
        k = QWidget(); kv = QVBoxLayout(k); row = QHBoxLayout()
        for text, fn in ((tr('import_files'), self.import_files), (tr('import_folder'), self.import_folder)):
            b = QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        self.kb_search = QLineEdit(); self.kb_search.setPlaceholderText('🔎'); self.kb_search.returnPressed.connect(self.search_kb); row.addWidget(self.kb_search, 1)
        dl = QPushButton(tr('delete')); dl.setObjectName('danger'); dl.clicked.connect(self.delete_doc); row.addWidget(dl); kv.addLayout(row)
        sp = QSplitter(Qt.Horizontal); self.doc_list = QListWidget(); self.doc_view = QTextBrowser(); sp.addWidget(self.doc_list); sp.addWidget(self.doc_view); sp.setSizes([420, 700])
        self.doc_list.itemClicked.connect(self.show_doc); kv.addWidget(sp, 1); tabs.addTab(k, tr('knowledge'))
        # memory
        m = QWidget(); mv = QVBoxLayout(m); row = QHBoxLayout()
        self.mem_input = QLineEdit(); self.mem_input.setPlaceholderText(tr('memory')); row.addWidget(self.mem_input, 1)
        ab = QPushButton(tr('add')); ab.clicked.connect(self.add_memory); row.addWidget(ab)
        db_ = QPushButton(tr('delete')); db_.setObjectName('danger'); db_.clicked.connect(self.delete_memory); row.addWidget(db_); mv.addLayout(row)
        self.mem_list = QListWidget(); mv.addWidget(self.mem_list, 1); tabs.addTab(m, tr('memory'))
        return page

    def refresh_library(self):
        if not hasattr(self, 'doc_list'): return
        self.doc_list.clear()
        for d in self.db.docs()[:2000]:
            it = QListWidgetItem(f"{d['name']}  ·  {d['chars']:,}"); it.setData(Qt.UserRole, d['id']); self.doc_list.addItem(it)
        self.mem_list.clear()
        for r in self.db.memories()[:2000]:
            it = QListWidgetItem(f"[{r['kind']}·{r['importance']}] {r['text']}"); it.setData(Qt.UserRole, r['id'])
            if rtl(r['text']): it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.mem_list.addItem(it)

    def show_doc(self, it):
        rows = self.db.query('SELECT content FROM knowledge_chunks WHERE doc_id=? ORDER BY chunk_index LIMIT 40', (it.data(Qt.UserRole),))
        self.doc_view.setMarkdown('\n\n'.join(r['content'] for r in rows))

    def search_kb(self):
        q = self.kb_search.text().strip()
        if not q: self.refresh_library(); return
        rows = KnowledgeBase(self.db).search(q, 30); self.doc_list.clear()
        for r in rows:
            it = QListWidgetItem(f"{r['name']}"); it.setData(Qt.UserRole, r['doc_id']); self.doc_list.addItem(it)
        self.doc_view.setMarkdown('\n\n---\n\n'.join(f"**{r['name']}**\n\n{r['content'][:1500]}" for r in rows[:8]))

    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, tr('import_files'), str(Path.home()))
        kb = KnowledgeBase(self.db)
        for p in paths:
            try: kb.import_file(p)
            except Exception as e: QMessageBox.warning(self, 'Aes', f'{Path(p).name}: {e}')
        self.refresh_library()

    def import_folder(self):
        d = QFileDialog.getExistingDirectory(self, tr('import_folder'), str(Path.home()))
        if not d: return
        self._start('library', lambda: self.tools._library_import(d))

    def delete_doc(self):
        it = self.doc_list.currentItem()
        if it and QMessageBox.question(self, tr('delete'), tr('delete') + '?') == QMessageBox.Yes:
            self.db.delete_doc(it.data(Qt.UserRole)); self.refresh_library()

    def add_memory(self):
        t = self.mem_input.text().strip()
        if t: self.db.add_memory(t, '', 'fact', 3); self.mem_input.clear(); self.refresh_library()

    def delete_memory(self):
        it = self.mem_list.currentItem()
        if it: self.db.delete_memory(it.data(Qt.UserRole)); self.refresh_library()

    # ---------------- models page ----------------
    def _page_models(self):
        page = QWidget(); v = QVBoxLayout(page); v.setContentsMargins(28, 22, 28, 22)
        v.addWidget(label(tr('models'), 'h1'))
        h = QHBoxLayout(); v.addLayout(h, 1)
        left = card(); lv = QVBoxLayout(left); self.model_list = QListWidget(); self.model_list.itemClicked.connect(self.load_model); lv.addWidget(self.model_list)
        nb = QPushButton('+'); nb.clicked.connect(self.new_model); lv.addWidget(nb); left.setFixedWidth(300); h.addWidget(left)
        form = card(); fl = QFormLayout(form); fl.setLabelAlignment(Qt.AlignLeft)
        self.mf = {k: QLineEdit() for k in ('name', 'model_path', 'endpoint', 'api_key', 'context_size', 'temperature', 'max_tokens')}
        self.mf['api_key'].setEchoMode(QLineEdit.Password)
        self.m_runtime = QComboBox(); self.m_runtime.addItems(list(RUNTIMES))
        fl.addRow('Name', self.mf['name']); fl.addRow('Runtime', self.m_runtime); fl.addRow('Model (GGUF path or id)', self.mf['model_path'])
        fl.addRow('Endpoint', self.mf['endpoint']); fl.addRow('API key (or env:NAME)', self.mf['api_key'])
        for k in ('context_size', 'temperature', 'max_tokens'): fl.addRow(k, self.mf[k])
        self.m_prompt = QPlainTextEdit(); self.m_prompt.setMinimumHeight(140); fl.addRow('System prompt', self.m_prompt)
        row = QHBoxLayout()
        for text, fn, name in ((tr('save'), self.save_model, 'primary'), (tr('test'), self.test_model, None), (tr('set_default'), self.default_model, None), (tr('delete'), self.delete_model, 'danger')):
            b = QPushButton(text); b.clicked.connect(fn)
            if name: b.setObjectName(name)
            row.addWidget(b)
        fl.addRow(row); h.addWidget(form, 1)
        hw = card(); hv = QVBoxLayout(hw); hv.addWidget(label(tr('hardware'), 'h2'))
        self.hw_view = QPlainTextEdit(); self.hw_view.setReadOnly(True); hv.addWidget(self.hw_view, 1)
        db_ = QPushButton(tr('doctor')); db_.clicked.connect(self.run_doctor); hv.addWidget(db_); hw.setFixedWidth(380); h.addWidget(hw)
        return page

    def refresh_models(self):
        if not hasattr(self, 'model_list'): return
        self.model_list.clear(); default = self.db.setting('default_model', '')
        for r in self.db.models():
            tag = f"☁ {tr('cloud_paid')}" if is_cloud(r) else f"● {tr('local_free')}"
            it = QListWidgetItem(('★ ' if r['name'] == default else '') + f"{r['name']}\n   {tag}"); it.setData(Qt.UserRole, r['name']); self.model_list.addItem(it)
            if r['name'] == default and not self.mf['name'].text(): self.model_list.setCurrentItem(it); self.load_model(it)
        self._fill_models()
        if not self.hw_view.toPlainText():
            from .hardware import doctor
            self.hw_view.setPlainText('…'); db = self.db
            threading.Thread(target=lambda: self.bridge.text_ready.emit('hw_view', doctor(db)), daemon=True).start()

    def load_model(self, it):
        r = self.db.model(it.data(Qt.UserRole))
        if not r: return
        for k in self.mf: self.mf[k].setText(str(r[k] if k in r.keys() else ''))
        self.m_runtime.setCurrentText(r['runtime']); self.m_prompt.setPlainText(r['system_prompt'])

    def new_model(self):
        for k, v in {'name': 'Aes Custom', 'model_path': 'qwen2.5-coder:7b', 'endpoint': 'http://127.0.0.1:11434/v1', 'api_key': '',
                     'context_size': '16384', 'temperature': '0.2', 'max_tokens': '4096'}.items(): self.mf[k].setText(v)
        self.m_runtime.setCurrentText('openai_compat')
        from .db import DEFAULT_SYSTEM
        self.m_prompt.setPlainText(DEFAULT_SYSTEM)

    def save_model(self):
        try:
            self.db.save_model(self.mf['name'].text().strip(), self.m_runtime.currentText(), self.mf['model_path'].text().strip(),
                               int(self.mf['context_size'].text() or 8192), -1, float(self.mf['temperature'].text() or 0.2),
                               int(self.mf['max_tokens'].text() or 2048), self.m_prompt.toPlainText().strip(), 1,
                               self.mf['endpoint'].text().strip(), self.mf['api_key'].text().strip())
            self.runtimes.unload(self.mf['name'].text().strip()); self.refresh_models()
        except Exception as e:
            QMessageBox.warning(self, 'Aes', str(e))

    def test_model(self):
        r = self.db.model(self.mf['name'].text().strip())
        if not r: return
        self.hw_view.setPlainText('…')
        self._start('model test', lambda: self.runtimes.complete(r, [{'role': 'user', 'content': 'Reply exactly: Aes model ready.'}]))

    def default_model(self):
        n = self.mf['name'].text().strip()
        if n: self.db.set_setting('default_model', n); self.refresh_models(); self._update_status()

    def delete_model(self):
        n = self.mf['name'].text().strip()
        if n and QMessageBox.question(self, tr('delete'), n + '?') == QMessageBox.Yes:
            self.db.delete_model(n); self.runtimes.unload(n); self.refresh_models()

    def run_doctor(self):
        from .hardware import doctor
        self.hw_view.setPlainText('…'); db = self.db
        self._start('doctor', lambda: doctor(db))

    # ---------------- tools / permissions page ----------------
    def _page_tools(self):
        page = QWidget(); v = QVBoxLayout(page); v.setContentsMargins(28, 22, 28, 22)
        v.addWidget(label(tr('tools'), 'h1'))
        self.tool_table = QTableWidget(0, 4); self.tool_table.setHorizontalHeaderLabels([tr('tool'), tr('risk'), tr('policy'), ''])
        self.tool_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch); self.tool_table.verticalHeader().setVisible(False)
        v.addWidget(self.tool_table, 1); return page

    def refresh_tools(self):
        if not hasattr(self, 'tool_table'): return
        pol = self.db.policies(); tools = list(self.tools.tools.values()); self.tool_table.setRowCount(len(tools))
        for i, t in enumerate(tools):
            self.tool_table.setItem(i, 0, QTableWidgetItem(t.name)); self.tool_table.setItem(i, 1, QTableWidgetItem(t.risk))
            cb = QComboBox(); cb.addItems(['allow', 'ask', 'deny']); cb.setCurrentText(pol.get(t.name, 'allow' if t.risk == 'safe' else 'ask'))
            cb.currentTextChanged.connect(lambda mode, n=t.name: self.db.set_policy(n, mode)); self.tool_table.setCellWidget(i, 2, cb)
            self.tool_table.setItem(i, 3, QTableWidgetItem(t.description))

    # ---------------- settings page ----------------
    def _page_settings(self):
        page = QWidget(); v = QVBoxLayout(page); v.setContentsMargins(28, 22, 28, 22)
        v.addWidget(label(tr('settings'), 'h1'))
        top = card(); f = QFormLayout(top)
        self.lang_box = QComboBox(); self.lang_box.addItem('English', 'en'); self.lang_box.addItem('العربية', 'ar')
        self.lang_box.setCurrentIndex(1 if I18N.lang == 'ar' else 0); self.lang_box.currentIndexChanged.connect(self.change_language)
        f.addRow(tr('language'), self.lang_box)
        dl = QHBoxLayout(); dl.addWidget(QLabel(str(DATA))); ob = QPushButton('📂'); ob.clicked.connect(lambda: self.open_path(DATA)); dl.addWidget(ob); dl.addStretch(1)
        f.addRow(tr('data_folder'), dl)
        tk = QHBoxLayout(); self.token_edit = QLineEdit(self.db.setting('hub_token', '')); self.token_edit.setEchoMode(QLineEdit.Password); self.token_edit.setReadOnly(True)
        tk.addWidget(self.token_edit, 1)
        cb = QPushButton(tr('copy')); cb.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.db.setting('hub_token', ''))); tk.addWidget(cb)
        rg = QPushButton(tr('regenerate')); rg.clicked.connect(self.regen_token); tk.addWidget(rg)
        f.addRow(tr('owner_api'), tk)
        self.steps = QSpinBox(); self.steps.setRange(3, 200); self.steps.setValue(int(self.db.setting('agent_max_steps', '30') or 30))
        self.steps.valueChanged.connect(lambda n: self.db.set_setting('agent_max_steps', str(n))); f.addRow(tr('max_steps'), self.steps)
        paths = {}
        for key, lab in (('blender_path', 'Blender'), ('unity_path', 'Unity'), ('rojo_path', 'Rojo')):
            e = QLineEdit(self.db.setting(key, '')); e.editingFinished.connect(lambda k=key, w=e: self.db.set_setting(k, w.text().strip())); f.addRow(lab, e)
        v.addWidget(top)
        idc = card(); iv = QVBoxLayout(idc); row = QHBoxLayout(); row.addWidget(label(tr('identity'), 'h2'))
        self.id_box = QComboBox(); self.id_box.addItems(['SOUL.md', 'IDENTITY.md', 'USER.md']); self.id_box.currentTextChanged.connect(self.load_identity); row.addWidget(self.id_box)
        sb = QPushButton(tr('save')); sb.setObjectName('primary'); sb.clicked.connect(self.save_identity); row.addWidget(sb); row.addStretch(1); iv.addLayout(row)
        self.id_edit = QPlainTextEdit(); iv.addWidget(self.id_edit, 1); v.addWidget(idc, 1)
        self.load_identity('SOUL.md')
        return page

    def change_language(self, _):
        self.db.set_setting('ui_language', self.lang_box.currentData())
        I18N.lang = self.lang_box.currentData()
        cid = self.cid; self._build()
        if cid: self.open_chat(cid)
        self.show_page('settings')

    def regen_token(self):
        import secrets
        self.db.set_setting('hub_token', secrets.token_urlsafe(32)); self.token_edit.setText(self.db.setting('hub_token'))

    def load_identity(self, name):
        p = IDENTITY_DATA / name
        self.id_edit.setPlainText(p.read_text(encoding='utf-8') if p.exists() else '')

    def save_identity(self):
        p = IDENTITY_DATA / self.id_box.currentText()
        if p.exists():
            hist = IDENTITY_DATA / 'history'; hist.mkdir(exist_ok=True)
            (hist / f"{p.stem}_{time.strftime('%Y%m%d_%H%M%S')}.md").write_text(p.read_text(encoding='utf-8'), encoding='utf-8')
        p.write_text(self.id_edit.toPlainText(), encoding='utf-8'); self.db.log('identity_edit', p.name, True)
        self.state_lbl.setText('✔ ' + p.name)

    # ---------------- misc ----------------
    def open_path(self, path):
        p = str(Path(path)); Path(p).mkdir(parents=True, exist_ok=True)
        if os.name == 'nt': os.startfile(p)
        else: webbrowser.open('file://' + p)

    def closeEvent(self, e):
        try:
            if self.busy: self.agent.cancel()
            self.runtimes.unload(); self.db.close()
        finally:
            e.accept()


def run(db_path):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Aes Studio'); app.setStyleSheet(QSS)
    w = AesWindow(db_path); w.show()
    return app.exec()
