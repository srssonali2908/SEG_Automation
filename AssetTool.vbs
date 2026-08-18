Option Explicit

' === Declarations ===
Dim fso, xlApp, xlBook, xlSheet, dataFile
Dim userChoice, title, email, architectEmail, clusterID, originID, assetType, assetTypePrefix
Dim lastRow, row, found

' === HARDCODED ARCHITECT EMAIL ===
architectEmail = "sonali.raj.sonal@altera.com"

' === File Path ===
Set fso = CreateObject("Scripting.FileSystemObject")
If fso Is Nothing Then Call HandleError(9999, "Failed to initialize Scripting.FileSystemObject.")
On Error Resume Next
rem dataFile = "Z:\techcomms\AssetTool\AssetData.xlsx"
Dim shell, userName
Set shell = CreateObject("WScript.Shell")
userName = CreateObject("WScript.Network").UserName

dataFile = "C:\Users\" & userName & "\Altera\Scale Enablement Group (SEG) - AssetID\AssetData.xlsx"

LogMessage "INFO: Data file path determined: " & dataFile
If Err.Number <> 0 Then Call HandleError(Err.Number, "Error determining absolute path for AssetData.xlsx. Ensure the file is accessible in the script directory.")
On Error GoTo 0

' === Get User Email (One-Time Setup) ===
email = GetOrSaveUserEmail()
LogMessage "INFO: User Email ID is: " & email

' === Initialize Excel ===
On Error Resume Next
Set xlApp = CreateObject("Excel.Application")
If Err.Number <> 0 Then Call HandleError(Err.Number, "Failed to launch Excel Application. Ensure Microsoft Excel is installed.")
On Error GoTo 0

xlApp.Visible = False
xlApp.DisplayAlerts = False

If Not fso.FileExists(dataFile) Then
    LogMessage "INFO: AssetData.xlsx not found. Creating a new file."
    On Error Resume Next
    Set xlBook = xlApp.Workbooks.Add()
    If Err.Number <> 0 Then Call HandleError(Err.Number, "Failed to create new Excel Workbook.")
    Set xlSheet = xlBook.Sheets(1)
    xlBook.SaveAs dataFile
    If Err.Number <> 0 Then Call HandleError(Err.Number, "Failed to save new Excel file to: " & dataFile & ". Check file permissions.")
    On Error GoTo 0
Else
    LogMessage "INFO: AssetData.xlsx found. Opening existing file."
    On Error Resume Next
    Set xlBook = xlApp.Workbooks.Open(dataFile)
    If Err.Number <> 0 Then Call HandleError(Err.Number, "Failed to open existing Excel file: " & dataFile & ". File might be corrupted or locked.")
    Set xlSheet = xlBook.Sheets(1)
    If Err.Number <> 0 Then Call HandleError(Err.Number, "Failed to access Sheet 1 of the Workbook.")
    On Error GoTo 0
End If

lastRow = GetLastRow() + 1
LogMessage "INFO: Next available Excel row: " & lastRow

' === User Choice ===
userChoice = InputBox("Enter 1 for New Asset or 2 for Existing Asset", "Asset Tool")

If userChoice = "1" Then
    ' === NEW ASSET ===
    
    ' PROMPT for Asset Type (DITA, Resource, or Markdown)
    assetType = InputBox("Enter Asset Type (DITA, Resource, or Markdown):", "New Asset Type")
    
    Select Case UCase(assetType)
        Case "DITA"
            assetTypePrefix = "D"
        Case "RESOURCE"
            assetTypePrefix = "R"
        Case "MARKDOWN"
            assetTypePrefix = "M"
        Case Else
            MsgBox "Invalid Asset Type entered. Exiting.", vbExclamation
            xlBook.Close False
            xlApp.Quit
            WScript.Quit
    End Select
    
    title = InputBox("Enter Asset Title:", "New Asset")
    ' Email is read automatically at script start
    
    LogMessage "TASK: Generating unique Cluster ID..."
    Do
        clusterID = GenerateID(assetTypePrefix)
    Loop While CheckDuplicate(clusterID, 1)

    LogMessage "TASK: Generating unique Origin ID..."
    Do
        originID = GenerateID(assetTypePrefix)
    Loop While CheckDuplicate(originID, 2)
    LogMessage "SUCCESS: IDs generated. Cluster ID: " & clusterID & ", Origin ID: " & originID

    ' === WRITE TO EXCEL (New Asset) ===
    On Error Resume Next
    xlSheet.Cells(lastRow, 1).Value = clusterID
    xlSheet.Cells(lastRow, 2).Value = originID
    xlSheet.Cells(lastRow, 3).Value = assetType
    xlSheet.Cells(lastRow, 4).Value = title
    xlSheet.Cells(lastRow, 5).Value = email
    xlSheet.Cells(lastRow, 6).Value = architectEmail
    If Err.Number <> 0 Then Call HandleError(Err.Number, "Error writing new asset data to Excel sheet.")
    On Error GoTo 0
    LogMessage "SUCCESS: Data written to Excel row " & lastRow

    MsgBox "New Asset Created." & vbNewLine & "Cluster ID: " & clusterID & vbNewLine & "Origin ID: " & originID & vbNewLine & "Asset Type: " & assetType

    SaveEntryToTextFile clusterID, originID, title, email, architectEmail, assetType
    SendEmailOutlook email, architectEmail, clusterID, originID, title, assetType

ElseIf userChoice = "2" Then
    ' === EXISTING ASSET ===
    clusterID = InputBox("Enter Existing Cluster ID (e.g., D123456):", "Existing Asset")
    ' Email is read automatically at script start
    title = InputBox("Enter Title:", "Existing Asset")

    ' --- Validation ---
    LogMessage "TASK: Searching for existing Cluster ID: " & clusterID
    found = False
    For row = 1 To GetLastRow()
        On Error Resume Next
        If Trim(CStr(xlSheet.Cells(row, 1).Value)) = Trim(clusterID) Then
    		found = True
    		Exit For
	End If

        If Err.Number <> 0 Then Call HandleError(Err.Number, "Error reading cluster ID from Excel row " & row & ".")
        On Error GoTo 0
    Next

    If Not found Then
        LogMessage "ERROR: Cluster ID " & clusterID & " not found."
        MsgBox "Cluster ID not found!", vbCritical
        xlBook.Close False
        xlApp.Quit
        WScript.Quit
    End If
    LogMessage "SUCCESS: Cluster ID " & clusterID & " found in Excel."
    
    ' *** FORCE RE-ENTRY OF ASSET TYPE ***
    assetType = InputBox("Enter Asset Type for the NEW Origin (DITA, Resource, or Markdown):", "Existing Asset Type Override")
    
    Select Case UCase(assetType)
        Case "DITA"
            assetTypePrefix = "D"
        Case "RESOURCE"
            assetTypePrefix = "R"
        Case "MARKDOWN"
            assetTypePrefix = "M"
        Case Else
            MsgBox "Invalid Asset Type entered for Origin. Exiting.", vbExclamation
            xlBook.Close False
            xlApp.Quit
            WScript.Quit
    End Select
    
    LogMessage "TASK: Generating unique Origin ID with prefix " & assetTypePrefix & "..."
    Do
        originID = GenerateID(assetTypePrefix) 
    Loop While CheckDuplicate(originID, 2)
    LogMessage "SUCCESS: Origin ID generated: " & originID

    ' === WRITE TO EXCEL (Existing Asset) ===
    On Error Resume Next
    xlSheet.Cells(lastRow, 1).Value = clusterID
    xlSheet.Cells(lastRow, 2).Value = originID
    xlSheet.Cells(lastRow, 3).Value = assetType
    xlSheet.Cells(lastRow, 4).Value = title
    xlSheet.Cells(lastRow, 5).Value = email
    xlSheet.Cells(lastRow, 6).Value = architectEmail
    If Err.Number <> 0 Then Call HandleError(Err.Number, "Error writing existing asset data to Excel sheet.")
    On Error GoTo 0
    LogMessage "SUCCESS: Origin data written to Excel row " & lastRow

    MsgBox "New Origin added." & vbNewLine & "Origin ID: " & originID & vbNewLine & "Asset Type: " & assetType

    SaveEntryToTextFile clusterID, originID, title, email, architectEmail, assetType
    SendEmailOutlook email, architectEmail, clusterID, originID, title, assetType

Else
    MsgBox "Invalid input. Exiting.", vbExclamation
End If

' === Save & Clean Up ===
LogMessage "TASK: Saving Excel and cleaning up..."
On Error Resume Next
xlBook.Save
If Err.Number <> 0 Then LogMessage "WARNING: Error during final save: " & Err.Description
xlBook.Close False
xlApp.Quit
Set xlSheet = Nothing
Set xlBook = Nothing
Set xlApp = Nothing
LogMessage "SUCCESS: Cleanup complete. Script finished."
On Error GoTo 0

' === PERSISTENCE FUNCTION ===

Function GetOrSaveUserEmail()
    Const configPath = "C:\AssetTool\user_config.txt"
    Dim userEmail, textFile, folderPath
    
    ' Ensure the AssetTool folder exists
    folderPath = Left(configPath, InStrRev(configPath, "\") - 1)
    If Not fso.FolderExists(folderPath) Then
        On Error Resume Next
        fso.CreateFolder(folderPath)
        If Err.Number <> 0 Then
            MsgBox "FATAL: Could not create config folder " & folderPath & ". Check permissions.", vbCritical
            WScript.Quit
        End If
        On Error GoTo 0
    End If

    If fso.FileExists(configPath) Then
        ' Read existing email
        On Error Resume Next
        Set textFile = fso.OpenTextFile(configPath, 1) ' 1 = ForReading
        If Err.Number <> 0 Then Call HandleError(Err.Number, "Could not read user config file. Please delete " & configPath & " and restart.")
        userEmail = textFile.ReadLine
        textFile.Close
        LogMessage "INFO: User email loaded from config file."
    Else
        ' Prompt and save email
        Do
            userEmail = InputBox("Welcome! Please enter your Email ID once (This will be saved for future use):", "Initial Setup")
            If Trim(userEmail) = "" Then
                MsgBox "Email ID cannot be empty. Please enter your email.", vbExclamation
            End If
        Loop While Trim(userEmail) = ""
        
        On Error Resume Next
        Set textFile = fso.CreateTextFile(configPath, True) ' True = Overwrite
        If Err.Number <> 0 Then Call HandleError(Err.Number, "Could not save user email to config file. Check permissions on " & configPath)
        textFile.WriteLine userEmail
        textFile.Close
        LogMessage "SUCCESS: User email saved to config file."
    End If
    
    GetOrSaveUserEmail = userEmail
End Function

' === LOGGING FUNCTION ===
Sub LogMessage(message)
    WScript.Echo message
End Sub

' === ERROR HANDLING FUNCTION ===

Sub HandleError(errNum, customMessage)
    LogMessage "!!! FATAL ERROR !!!"
    MsgBox "--- FATAL ERROR ---" & vbNewLine & _
           "Code: " & errNum & vbNewLine & _
           "Description: " & Err.Description & vbNewLine & vbNewLine & _
           "Action Required: " & customMessage, vbCritical, "Asset Tool Error"
    
    ' Attempt cleanup before exiting
    On Error Resume Next
    If Not xlBook Is Nothing Then xlBook.Close False
    If Not xlApp Is Nothing Then xlApp.Quit
    On Error GoTo 0
    
    WScript.Quit
End Sub

' === UTILITY FUNCTIONS ===

Function GenerateID(idPrefix)
    Randomize
    If Len(idPrefix) = 0 Then idPrefix = "U" 
    GenerateID = idPrefix & Right("000000" & Int(Rnd * 999999 + 1), 6)
End Function

Function CheckDuplicate(idToCheck, colNum)
    Dim i
    CheckDuplicate = False
    For i = 1 To GetLastRow()
        If xlSheet.Cells(i, colNum).Value = idToCheck Then
            CheckDuplicate = True
            Exit Function
        End If
    Next
End Function

Function GetLastRow()
    Dim i
    i = 1
    Do While xlSheet.Cells(i, 1).Value <> ""
        i = i + 1
    Loop
    GetLastRow = i - 1
End Function

Sub SendEmailOutlook(toEmail, ccEmail, clusterID, originID, title, assetType)
    LogMessage "TASK: Attempting to send Outlook email..."
    On Error Resume Next

    Dim objOutlook, objMail, bodyText

    Set objOutlook = CreateObject("Outlook.Application")
    If objOutlook Is Nothing Then
        MsgBox "Outlook is not installed or accessible. Skipping email notification.", vbExclamation
        LogMessage "WARNING: Outlook not available. Email skipped."
        Exit Sub
    End If

    Set objMail = objOutlook.CreateItem(0)  ' olMailItem = 0

    bodyText = "Hello," & vbNewLine & vbNewLine & _
               "A new asset entry has been created/updated with the following details:" & vbNewLine & vbNewLine & _
               "Asset Type : " & assetType & vbNewLine & _
               "Title      : " & title & vbNewLine & _
               "Cluster ID : " & clusterID & vbNewLine & _
               "Origin ID  : " & originID & vbNewLine & vbNewLine & _
               "Requested By: " & toEmail & vbNewLine & _
               "Architect  : " & ccEmail & vbNewLine & vbNewLine & _
               "This is an automated message."

    With objMail
        .To = toEmail
        .CC = ccEmail
        .Subject = "Asset Entry Created/Updated: " & title
        .Body = bodyText
        .Send
    End With

    If Err.Number <> 0 Then
        MsgBox "Outlook Error occurred while sending email: " & Err.Description, vbCritical
        LogMessage "ERROR: Outlook failed to send email: " & Err.Description
    Else
        LogMessage "SUCCESS: Email notification sent to " & toEmail
    End If

    Set objMail = Nothing
    Set objOutlook = Nothing
End Sub

Sub SaveEntryToTextFile(clusterID, originID, title, email, architectEmail, assetType)
    LogMessage "TASK: Attempting to save entry to text file..."
    Dim savePath, txtFile, entryText

    savePath = "C:\AssetTool\entries\"

    ' Create folder if it doesn't exist
    Dim fsoInner
    On Error Resume Next
    Set fsoInner = CreateObject("Scripting.FileSystemObject")
    If Err.Number <> 0 Then
        MsgBox "File system object failed to initialize. Cannot save text file.", vbCritical
        LogMessage "ERROR: File system object failed. Cannot save text file."
        Exit Sub
    End If
    
    If Not fsoInner.FolderExists(savePath) Then
        fsoInner.CreateFolder(savePath)
        LogMessage "INFO: Created directory: " & savePath
    End If
    
    If Err.Number <> 0 Then
        MsgBox "Failed to create folder: " & savePath & ". Check file permissions.", vbCritical
        LogMessage "ERROR: Failed to create folder: " & savePath
        Exit Sub
    End If
    On Error GoTo 0

    ' Build the full file name (Asset_CLUSTERID_ORIGINID.txt)
    Dim fileName
    fileName = "Asset_" & clusterID & "_" & originID & ".txt"

    ' Entry content
    entryText = "Asset Entry Details" & vbNewLine & String(30, "-") & vbNewLine & _
                "Asset Type : " & assetType & vbNewLine & _
                "Title      : " & title & vbNewLine & _
                "Cluster ID : " & clusterID & vbNewLine & _
                "Origin ID  : " & originID & vbNewLine & _
                "Requested By: " & email & vbNewLine & _
                "Architect  : " & architectEmail & vbNewLine & _
                "Date       : " & Now & vbNewLine

    ' Write to file
    On Error Resume Next
    Set txtFile = fsoInner.CreateTextFile(savePath & fileName, True)
    If Err.Number <> 0 Then
        MsgBox "Failed to create/write to text file: " & savePath & fileName & ". Check file permissions.", vbCritical
        LogMessage "ERROR: Failed to create/write text file: " & savePath & fileName
        Exit Sub
    End If
    
    txtFile.Write entryText
    txtFile.Close
    LogMessage "SUCCESS: Text file saved: " & savePath & fileName

    Set txtFile = Nothing
    Set fsoInner = Nothing
    On Error GoTo 0
    
End Sub