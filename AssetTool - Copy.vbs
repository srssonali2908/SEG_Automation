Option Explicit

Dim fso, xlApp, xlBook, xlSheet, dataFile
Dim userChoice, title, email, manager, clusterID, originID
Dim lastRow, row, existingCluster, found, idExists

' File path
dataFile = CreateObject("Scripting.FileSystemObject").GetAbsolutePathName("AssetData.xlsx")

' Initialize Excel
Set xlApp = CreateObject("Excel.Application")
xlApp.Visible = False
xlApp.DisplayAlerts = False

' Open or create workbook
If Not CreateObject("Scripting.FileSystemObject").FileExists(dataFile) Then
    Set xlBook = xlApp.Workbooks.Add()
    Set xlSheet = xlBook.Sheets(1)
    xlSheet.Cells(1,1).Value = "Cluster ID"
    xlSheet.Cells(1,2).Value = "Origin ID"
    xlSheet.Cells(1,3).Value = "Title"
    xlSheet.Cells(1,4).Value = "Email"
    xlSheet.Cells(1,5).Value = "Manager"
    xlBook.SaveAs dataFile
Else
    Set xlBook = xlApp.Workbooks.Open(dataFile)
    Set xlSheet = xlBook.Sheets(1)
End If

lastRow = xlSheet.UsedRange.Rows.Count + 1

' Ask if new or existing
userChoice = InputBox("Enter 1 for New Asset or 2 for Existing Asset", "Asset Tool")

If userChoice = "1" Then
    ' NEW ASSET
    title = InputBox("Enter Asset Title:", "New Asset")
    email = InputBox("Enter Email ID:", "New Asset")
    manager = InputBox("Enter Manager Name:", "New Asset")

    Do
        clusterID = GenerateID()
    Loop While CheckDuplicate(clusterID, 1)

    Do
        originID = GenerateID()
    Loop While CheckDuplicate(originID, 2)

    ' Save data
    xlSheet.Cells(lastRow, 1).Value = clusterID
    xlSheet.Cells(lastRow, 2).Value = originID
    xlSheet.Cells(lastRow, 3).Value = title
    xlSheet.Cells(lastRow, 4).Value = email
    xlSheet.Cells(lastRow, 5).Value = manager

    MsgBox "New Asset Created." & vbCrLf & "Cluster ID: " & clusterID & vbCrLf & "Origin ID: " & originID

ElseIf userChoice = "2" Then
    ' EXISTING ASSET
    clusterID = InputBox("Enter Existing Cluster ID (e.g., U123456):", "Existing Asset")
    email = InputBox("Enter Email ID:", "Existing Asset")
    title = InputBox("Enter Title:", "Existing Asset")
    manager = InputBox("Enter Manager:", "Existing Asset")

    found = False
    For row = 2 To xlSheet.UsedRange.Rows.Count
        If xlSheet.Cells(row, 1).Value = clusterID Then
            found = True
            Exit For
        End If
    Next

    If Not found Then
        MsgBox "Cluster ID not found!", vbCritical
        xlBook.Close True
        xlApp.Quit
        WScript.Quit
    End If

    Do
        originID = GenerateID()
    Loop While CheckDuplicate(originID, 2)

    ' Add entry with same Cluster ID and new Origin ID
    xlSheet.Cells(lastRow, 1).Value = clusterID
    xlSheet.Cells(lastRow, 2).Value = originID
    xlSheet.Cells(lastRow, 3).Value = title
    xlSheet.Cells(lastRow, 4).Value = email
    xlSheet.Cells(lastRow, 5).Value = manager

    MsgBox "New Origin added for Existing Cluster." & vbCrLf & "Origin ID: " & originID

Else
    MsgBox "Invalid choice. Exiting."
End If

' Save and close
xlBook.Save
xlBook.Close False
xlApp.Quit

Set xlSheet = Nothing
Set xlBook = Nothing
Set xlApp = Nothing

' ===== FUNCTIONS =====
Function GenerateID()
    Randomize
    GenerateID = "U" & Right("000000" & Int(Rnd * 999999 + 1), 6)
End Function

Function CheckDuplicate(idToCheck, colNum)
    Dim i
    CheckDuplicate = False
    For i = 2 To xlSheet.UsedRange.Rows.Count
        If xlSheet.Cells(i, colNum).Value = idToCheck Then
            CheckDuplicate = True
            Exit Function
        End If
    Next
End Function
