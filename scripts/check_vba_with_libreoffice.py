"""Run the VBA macro without Excel, using LibreOffice in VBA compatibility mode.

This is a check for developers: it proves vba/FootprintModel.bas runs and
gives the same answer as the Excel formulas (and therefore the Python model).

Requirements: LibreOffice installed, and its Python UNO bridge (import uno).
Usage:
    python scripts/check_vba_with_libreoffice.py
Writes outputs/tables/vba_check.csv and prints a summary.
"""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import uno  # noqa: F401  (LibreOffice Python bridge)
from com.sun.star.beans import PropertyValue

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "excel" / "Retail_Footprint_Expansion_Model.xlsx"
MODULE = ROOT / "vba" / "FootprintModel.bas"
PORT = 2099


def prepare_code() -> str:
    code = MODULE.read_text(encoding="utf-8")
    code = "\n".join(line for line in code.splitlines() if not line.startswith("Attribute "))
    code = code.replace("Option Explicit", "Option VBASupport 1\nOption Explicit", 1)
    # Screen related calls need a visible window, which a headless check does not have
    for line in ("    Application.ScreenUpdating = False\n", "    Application.ScreenUpdating = True\n", "    wsOut.Activate\n", "    Application.Calculate\n"):
        code = code.replace(line, "")
    # Worksheet functions also need a window here. Excel ROUND(x, 0) for positive x equals Int(x + 0.5)
    code = code.replace(
        "targetPop = Application.WorksheetFunction.Round( _\n            wsData.Cells(r, COL_POPULATION).Value * wsData.Cells(r, COL_LSM).Value, 0)",
        "targetPop = Int(wsData.Cells(r, COL_POPULATION).Value * wsData.Cells(r, COL_LSM).Value + 0.5)",
    )
    # A message box would wait forever without a screen, so write the message to a cell instead
    start = code.index('    MsgBox "Done. "')
    end = code.index("End Sub", start)
    message = code[start:end].replace("MsgBox ", 'wsOut.Range("G1").Value = ', 1)
    message = message[: message.rindex("mismatches") + len("mismatches")] + "\n"
    code = code[:start] + message + code[end:]
    # Report runtime errors in a cell
    code = code.replace("    Dim wsData As Worksheet, wsModel", "    On Error GoTo Fail\n    Dim wsData As Worksheet, wsModel", 1)
    first_end = code.index("End Sub")
    handler = '    Exit Sub\nFail:\n    ThisWorkbook.Worksheets("Macro Results").Range("H1").Value = "ERROR " & Err.Number & ": " & Err.Description\n'
    return code[:first_end] + handler + code[first_end:]


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main() -> None:
    work = Path(tempfile.mkdtemp())
    book = work / "model.xlsx"
    shutil.copy(WORKBOOK, book)
    env = os.environ.copy()
    env["SAL_USE_VCLPLUGIN"] = "svp"
    office = subprocess.Popen(
        ["soffice", "--headless", "--invisible", "--norestore", f"-env:UserInstallation=file://{work}/profile",
         f"--accept=socket,host=127.0.0.1,port={PORT};urp;"],
        env=env,
    )
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        ctx = None
        for _ in range(60):
            try:
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={PORT};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(1)
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        doc = desktop.loadComponentFromURL(book.as_uri(), "_blank", 0, (prop("Hidden", True), prop("MacroExecutionMode", 4)))
        libs = doc.BasicLibraries
        if not libs.hasByName("Standard"):
            libs.createLibrary("Standard")
        lib = libs.getByName("Standard")
        lib.insertByName("FootprintModel", prepare_code())
        libs.VBACompatibilityMode = True
        script = doc.getScriptProvider().getScript(
            "vnd.sun.star.script:Standard.FootprintModel.RunFootprintModel?language=Basic&location=document"
        )
        started = time.time()
        script.invoke((), (), ())
        seconds = time.time() - started

        sheet = doc.Sheets.getByName("Macro Results")
        error = sheet.getCellRangeByName("H1").getString()
        message = sheet.getCellRangeByName("G1").getString()
        rows = []
        r = 4
        while sheet.getCellByPosition(0, r).getString():
            rows.append([sheet.getCellByPosition(c, r).getString() for c in range(5)])
            r += 1
        doc.close(True)
    finally:
        try:
            desktop.terminate()
        except Exception:
            pass
        office.terminate()
        office.wait(timeout=30)

    if error:
        sys.exit(f"Macro failed: {error}")
    out = ROOT / "outputs" / "tables" / "vba_check.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["district", "recommended_macro", "limiting_factor_macro", "recommended_model_sheet", "match"])
        w.writerows(rows)
    print(message.replace("\n", " | "))
    print(f"Districts: {len(rows)}. Mismatches: {sum(row[4] != 'Yes' for row in rows)}. Macro run time: {seconds:.1f} s")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
