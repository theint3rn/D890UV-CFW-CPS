#!/bin/sh
# Stand-alone x86-64 binaries of the desktop CPS (CLI + Tkinter GUI in one file) with PyInstaller.
#
#   tools/build_exe.sh linux      -> dist/cfw_cps-linux-x86_64
#   tools/build_exe.sh windows    -> dist/cfw_cps-windows-x64.exe   (PyInstaller under Wine)
#
# linux:   uses $PY (default python3). If PyInstaller is missing it makes a venv in build/venv and pip-installs it.
# windows: on a Windows machine just run (in cfw_cps\):
#              py -m pip install pyinstaller && py -m PyInstaller --onefile --name cfw_cps-windows-x64 --distpath dist cfw_cps.py
#          Here (Linux) it uses Wine with WINEPREFIX, which must be set and must not be ~/.wine (project rule).
#          The prefix needs a Windows x64 Python with Tcl/Tk; give an installer with PY_WIN_INSTALLER=python-3.x-amd64.exe
#          (from python.org) and it is installed into the prefix first.
# The binaries contain the codeplug CPS only (no firmware flashing).
set -eu
cd "$(dirname "$0")/.."
what=${1:-linux}
mkdir -p dist build

if [ "$what" = linux ]; then
    PY=${PY:-python3}
    if ! "$PY" -c "import PyInstaller" 2>/dev/null; then
        [ -x build/venv/bin/python ] || "$PY" -m venv --system-site-packages build/venv
        build/venv/bin/pip install -q pyinstaller
        PY=build/venv/bin/python
    fi
    "$PY" -m PyInstaller --noconfirm --clean --onefile --name cfw_cps-linux-x86_64 \
        --distpath dist --workpath build/pyi-linux --specpath build --add-data "$(pwd)/schema:schema" \
        --hidden-import cps.gui --hidden-import cps.import_rdt --hidden-import cps.import_csv --hidden-import cps.import_nand \
        --hidden-import cps.stock --hidden-import cps.report --hidden-import cps.rdt cfw_cps.py
    ls -l dist/cfw_cps-linux-x86_64
elif [ "$what" = windows ]; then
    : "${WINEPREFIX:?set WINEPREFIX to a scratch Wine prefix (never ~/.wine)}"
    case "$(readlink -f "$WINEPREFIX")" in "$(readlink -f "$HOME")/.wine") echo "refusing ~/.wine" >&2; exit 1;; esac
    export WINEPREFIX WINEDEBUG=-all
    WPY='C:\py\python.exe'
    if ! wine "$WPY" -V >/dev/null 2>&1; then
        : "${PY_WIN_INSTALLER:?no Python in the prefix: set PY_WIN_INSTALLER=python-3.x-amd64.exe}"
        wine "$PY_WIN_INSTALLER" /quiet InstallAllUsers=0 TargetDir='C:\py' Include_tcltk=1 Include_test=0 \
            Include_launcher=0 Shortcuts=0 AssociateFiles=0 PrependPath=0
    fi
    wine "$WPY" -m pip install -q pyinstaller
    wine "$WPY" -m PyInstaller --noconfirm --clean --onefile --name cfw_cps-windows-x64 \
        --distpath dist --workpath build/pyi-win --specpath build --add-data "$(winepath -w "$(pwd)/schema");schema" \
        --hidden-import cps.gui --hidden-import cps.import_rdt --hidden-import cps.import_csv --hidden-import cps.import_nand \
        --hidden-import cps.stock --hidden-import cps.report --hidden-import cps.rdt cfw_cps.py
    ls -l dist/cfw_cps-windows-x64.exe
else
    echo "usage: $0 linux|windows" >&2
    exit 2
fi
