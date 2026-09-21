Option Explicit
Dim sh, fs, root, target, command
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
target = Chr(34) & root & "\bootstrap.pyw" & Chr(34)
sh.CurrentDirectory = root
On Error Resume Next
sh.Run "py -3 " & target, 0, False
If Err.Number <> 0 Then
    Err.Clear
    sh.Run "pythonw " & target, 0, False
    If Err.Number <> 0 Then
        MsgBox "Python was not found. Install Python 3.10 or newer from python.org, then double-click Start Workbench again.", 48, "RPG Testing"
    End If
End If
