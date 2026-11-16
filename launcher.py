"""Open an app window; closing that window shuts down this server and its worker trees."""
import os
import subprocess
import tempfile
import threading
import ctypes
from pathlib import Path
from workbench_server import create_server,stop_jobs


def browser_executable():
    paths=[Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
        Path(os.environ.get('LOCALAPPDATA',''))/'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    return next((p for p in paths if p.is_file()),None)


def main():
    try:
        from native_window import show_window
    except ImportError:
        show_window=None
    if show_window:
        server=create_server();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:show_window(server,thread)
        finally:stop_jobs();server.shutdown();server.server_close()
        return
    browser=browser_executable()
    if not browser:raise RuntimeError('请先安装Chrome或Microsoft Edge，再启动工作台。')
    server=create_server();thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='listing-workbench-',ignore_cleanup_errors=True) as profile:
            process=subprocess.Popen([str(browser),f'--app=http://127.0.0.1:{server.server_port}',
                '--user-data-dir='+profile,'--no-first-run','--no-default-browser-check','--disable-background-mode',
                '--disable-extensions','--window-size=880,560','--remote-debugging-port=0'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            def wait_for_close():
                process.wait();server.shutdown()
            threading.Thread(target=wait_for_close,daemon=True).start()
            thread.join()
            stop_jobs()
            if process.poll() is None:process.terminate();process.wait(timeout=10)
    finally:
        stop_jobs();server.server_close()


if __name__=='__main__':
    try:main()
    except Exception as error:
        if os.name=='nt':ctypes.windll.user32.MessageBoxW(0,str(error),'电商素材工作台',0x10)
        else:raise
