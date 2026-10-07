Attribute VB_Name = "FootprintModel"
'==============================================================================
' Retail Footprint Expansion Model: one click outlet recommendation (VBA)
'
' WHAT IT DOES
'   The original model needed Goal Seek to be run by hand for every district.
'   This macro does it for all districts in one click.
'
'   For each district on the "District Data" sheet it adds new outlets
'   (one outlet = one freezer) one at a time, and stops as soon as one more
'   outlet would push:
'     * TP  (Throughput, liters per freezer per week) below the Ideal TP, or
'     * PPO (Population Per Outlet) below the Ideal PPO.
'   Districts already at or below either line get no new outlets.
'
'   Results go to the "Macro Results" sheet, next to the answer from the
'   formulas on the "Model" sheet, so anyone can see that both agree.
'
' HOW TO USE
'   1. Open Retail_Footprint_Expansion_Model.xlsx in Excel.
'   2. Open the Visual Basic Editor:
'        Windows: Alt + F11.   Mac: Tools > Macro > Visual Basic Editor.
'   3. File > Import File..., then choose this file (FootprintModel.bas).
'   4. Save the workbook as an Excel Macro-Enabled Workbook (.xlsm).
'   5. Run it: Tools (or Developer) > Macros > RunFootprintModel > Run.
'
' Works on Excel for Windows and Excel for Mac (no Windows-only libraries).
' All data in the workbook is SIMULATED. It is not real company data.
'==============================================================================
Option Explicit

Private Const FIRST_ROW As Long = 5

' Column positions on the "District Data" sheet
Private Const COL_DISTRICT As Long = 1
Private Const COL_REGION As Long = 3
Private Const COL_POPULATION As Long = 5
Private Const COL_LSM As Long = 6
Private Const COL_OUTLETS As Long = 9
Private Const COL_VOLUME As Long = 12
Private Const COL_NI_OUTLETS As Long = 13
Private Const COL_NI_VOLUME As Long = 14

' Column of "RECOMMENDED NEW OUTLETS" on the "Model" sheet (column U)
Private Const COL_MODEL_RECOMMENDED As Long = 21

Public Sub RunFootprintModel()
    Dim wsData As Worksheet, wsModel As Worksheet, wsOut As Worksheet
    Set wsData = ThisWorkbook.Worksheets("District Data")
    Set wsModel = ThisWorkbook.Worksheets("Model")
    Set wsOut = ThisWorkbook.Worksheets("Macro Results")

    ' Step 1: read the settings from the Inputs sheet (named cells)
    Dim idealTP As Double, idealPPO As Double, weeks As Double, firstFill As Double
    Dim basis As String
    idealTP = ThisWorkbook.Names("IdealTP").RefersToRange.Value
    idealPPO = ThisWorkbook.Names("IdealPPO").RefersToRange.Value
    weeks = ThisWorkbook.Names("Weeks").RefersToRange.Value
    firstFill = ThisWorkbook.Names("FirstFill").RefersToRange.Value
    basis = ThisWorkbook.Names("TPBasis").RefersToRange.Value

    Application.ScreenUpdating = False
    Application.Calculate

    ' Find the last district row (the list ends at the first empty cell)
    Dim lastRow As Long
    lastRow = FIRST_ROW - 1
    Do While Len(wsData.Cells(lastRow + 1, COL_DISTRICT).Value) > 0
        lastRow = lastRow + 1
    Loop
    wsOut.Range("A" & FIRST_ROW & ":E" & (FIRST_ROW + 2000)).ClearContents

    Dim r As Long, outRow As Long, mismatches As Long, totalNew As Double
    outRow = FIRST_ROW

    For r = FIRST_ROW To lastRow
        ' Step 2: read this district's numbers
        Dim outlets As Double, volume As Double, targetPop As Double, outletTP As Double
        outlets = wsData.Cells(r, COL_OUTLETS).Value
        volume = wsData.Cells(r, COL_VOLUME).Value
        targetPop = Application.WorksheetFunction.Round( _
            wsData.Cells(r, COL_POPULATION).Value * wsData.Cells(r, COL_LSM).Value, 0)

        ' Step 3: throughput assumed for every new outlet
        outletTP = NewOutletTP(wsData, r, lastRow, weeks, basis, outlets, volume)

        ' Step 4: add outlets one at a time until a limit is reached
        Dim n As Long, why As String
        n = OutletsToAdd(outlets, volume, targetPop, outletTP, idealTP, idealPPO, weeks, firstFill, why)

        ' Step 5: write the result and compare with the Model sheet formula
        Dim formulaValue As Variant
        formulaValue = wsModel.Cells(r, COL_MODEL_RECOMMENDED).Value
        wsOut.Cells(outRow, 1).Value = wsData.Cells(r, COL_DISTRICT).Value
        wsOut.Cells(outRow, 2).Value = n
        wsOut.Cells(outRow, 3).Value = why
        wsOut.Cells(outRow, 4).Value = formulaValue
        If CLng(formulaValue) = n Then
            wsOut.Cells(outRow, 5).Value = "Yes"
        Else
            wsOut.Cells(outRow, 5).Value = "No"
            mismatches = mismatches + 1
        End If
        totalNew = totalNew + n
        outRow = outRow + 1
    Next r

    Application.ScreenUpdating = True
    wsOut.Activate
    MsgBox "Done. " & (lastRow - FIRST_ROW + 1) & " districts processed." & vbCrLf & _
           "Recommended new outlets (Phase 1 demand): " & Format(totalNew, "#,##0") & vbCrLf & _
           "Districts where the macro and the Model sheet disagree: " & mismatches, _
           vbInformation, "Retail Footprint Expansion Model"
End Sub

' Throughput (liters per freezer per week) assumed for each new outlet.
'   "NI TP": throughput of retailers that got a freezer last year (the original method).
'            If the district had no new retailers, use the average for its sales region.
'   "District TP": average throughput of all retailers in the district.
Private Function NewOutletTP(ws As Worksheet, r As Long, lastRow As Long, weeks As Double, _
                             basis As String, outlets As Double, volume As Double) As Double
    If basis <> "NI TP" Then
        If outlets > 0 Then NewOutletTP = volume / (outlets * weeks)
        Exit Function
    End If

    Dim niOutlets As Double, niVolume As Double
    niOutlets = ws.Cells(r, COL_NI_OUTLETS).Value
    niVolume = ws.Cells(r, COL_NI_VOLUME).Value
    If niOutlets > 0 And niVolume > 0 Then
        NewOutletTP = niVolume / (niOutlets * weeks)
        Exit Function
    End If

    ' No new retailers in this district: use the sales region average
    Dim i As Long, region As String, sumVol As Double, sumOutlets As Double
    region = ws.Cells(r, COL_REGION).Value
    For i = FIRST_ROW To lastRow
        If ws.Cells(i, COL_REGION).Value = region Then
            sumVol = sumVol + ws.Cells(i, COL_NI_VOLUME).Value
            sumOutlets = sumOutlets + ws.Cells(i, COL_NI_OUTLETS).Value
        End If
    Next i
    If sumOutlets > 0 Then NewOutletTP = sumVol / (sumOutlets * weeks)
End Function

' How many outlets to add in one district. The reason is returned in "why".
Private Function OutletsToAdd(outlets As Double, volume As Double, targetPop As Double, _
                              outletTP As Double, idealTP As Double, idealPPO As Double, _
                              weeks As Double, firstFill As Double, ByRef why As String) As Long
    Dim n As Long
    n = 0

    If outlets <= 0 Then
        why = "No current outlets"
    ElseIf volume / outlets / weeks <= idealTP Then
        why = "TP already at or below ideal"
    ElseIf targetPop / outlets <= idealPPO Then
        why = "PPO already at or below ideal"
    Else
        Dim nextTP As Double, nextPPO As Double, tpFails As Boolean, ppoFails As Boolean
        Do
            ' What would TP and PPO be with one more outlet?
            nextTP = (volume + (n + 1) * (weeks * outletTP + firstFill)) / (outlets + n + 1) / weeks
            nextPPO = targetPop / (outlets + n + 1)
            tpFails = (nextTP < idealTP)
            ppoFails = (nextPPO < idealPPO)
            If tpFails Or ppoFails Then Exit Do
            n = n + 1
        Loop

        If tpFails And ppoFails Then
            ' Both limits are crossed by the same outlet: name the one reached first
            If TPLimit(outlets, volume, outletTP, idealTP, weeks, firstFill) <= targetPop / idealPPO - outlets Then
                why = "Stopped by TP reaching ideal"
            Else
                why = "Stopped by PPO reaching ideal"
            End If
        ElseIf tpFails Then
            why = "Stopped by TP reaching ideal"
        Else
            why = "Stopped by PPO reaching ideal"
        End If
    End If
    OutletsToAdd = n
End Function

' Exact (not whole number) outlets at which TP equals the ideal. Used only to break ties.
Private Function TPLimit(outlets As Double, volume As Double, outletTP As Double, _
                         idealTP As Double, weeks As Double, firstFill As Double) As Double
    Dim gap As Double
    gap = idealTP * weeks - (weeks * outletTP + firstFill)
    If gap > 0 Then
        TPLimit = (volume - idealTP * weeks * outlets) / gap
    Else
        TPLimit = 1E+30
    End If
End Function
