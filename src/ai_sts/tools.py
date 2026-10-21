import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

tools = []

def register(fn):
    tools.append(fn)
    return fn

@register
def current_time() -> str:
    """current date and time"""
    return str(datetime.now())

@register
def read_file(path: str) -> str:
    """read a text file"""
    return Path(path).read_text(encoding="utf-8")[:5000]

@register
def fetch_url(url: str) -> str:
    """get the text of a web page"""
    with urllib.request.urlopen(url, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="ignore")[:3000]

@register
def run_command(command: str) -> str:
    """run a shell command (asks the user first)"""
    if input(f"run '{command}'? y/n ").lower() != "y":
        return "cancelled"
    out = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    return (out.stdout + out.stderr)[:3000]