"""Small frameless shell. The existing local server still owns all project work."""
import sys
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QTimer,QObject,Signal,QEvent
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QSizeGrip,QFileDialog
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings


def show_window(server,server_thread):
    app=QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName('拾词')
    class Clipboard(QObject):
        copied=Signal(str)
    clipboard=Clipboard();clipboard.copied.connect(lambda text:app.clipboard().setText(text))
    server.copy_text=clipboard.copied.emit

    class DragArea(QWidget):
        def mousePressEvent(self,event):
            if event.button()==Qt.MouseButton.LeftButton:self.window().windowHandle().startSystemMove()
        def mouseDoubleClickEvent(self,event):
            if event.button()==Qt.MouseButton.LeftButton:toggle_maximize()

    class AppWindow(QWidget):
        def changeEvent(self,event):
            super().changeEvent(event)
            if event.type()==QEvent.Type.WindowStateChange and hasattr(self,'maximize_button'):
                maximized=self.isMaximized()
                button=self.maximize_button
                button.setText('❐' if maximized else '□')
                button.setAccessibleName('恢复' if maximized else '最大化')
                button.setToolTip(button.accessibleName())
                if hasattr(self,'grip'):self.grip.setVisible(not maximized)

    window=AppWindow();window.setWindowTitle('拾词')
    def toggle_maximize():
        window.showNormal() if window.isMaximized() else window.showMaximized()
    window.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
    window.setStyleSheet('QWidget{background:white} QPushButton{border:0;color:#999;font-size:16px;background:white;border-radius:10px} QPushButton:hover{background:#f0f0f0;color:#222}')
    layout=QVBoxLayout(window);layout.setContentsMargins(1,1,1,1);layout.setSpacing(0)
    bar=DragArea();bar.setFixedHeight(30)
    controls=QHBoxLayout(bar);controls.setContentsMargins(12,1,10,1);controls.setSpacing(4);controls.addStretch()
    for label,hint,callback in [('−','最小化',window.showMinimized),('□','最大化',toggle_maximize),('×','关闭',window.close)]:
        button=QPushButton(label);button.setAccessibleName(hint);button.setToolTip(hint);button.setFixedSize(28,24);button.clicked.connect(callback);controls.addWidget(button)
        if hint=='最大化':window.maximize_button=button
    layout.addWidget(bar)
    view=QWebEngineView();view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,True)
    view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste,True)
    view.load(QUrl(f'http://127.0.0.1:{server.server_port}'))
    layout.addWidget(view,1)
    grip_row=QHBoxLayout();grip_row.setContentsMargins(0,0,0,0);grip_row.addStretch()
    grip=QSizeGrip(window);grip.setFixedSize(12,10);grip_row.addWidget(grip);layout.addLayout(grip_row)
    window.grip=grip
    def download(item):
        destination,_=QFileDialog.getSaveFileName(window,'保存文件',str(Path.home()/'Downloads'/item.downloadFileName()))
        if not destination:item.cancel();return
        item.setDownloadDirectory(str(Path(destination).parent));item.setDownloadFileName(Path(destination).name);item.accept()
    view.page().profile().downloadRequested.connect(download)
    available=app.primaryScreen().availableGeometry()
    width=min(880,int(available.width()*.82));height=min(560,int(available.height()*.82))
    window.resize(width,height);window.setMinimumSize(min(660,width),min(420,height))
    window.move(available.x()+(available.width()-width)//2,available.y()+(available.height()-height)//2)
    # An explicit server shutdown also closes the shell; ordinary close exits app.exec.
    timer=QTimer(window);timer.timeout.connect(lambda:window.close() if not server_thread.is_alive() else None);timer.start(300)
    window.show()
    app.exec()

