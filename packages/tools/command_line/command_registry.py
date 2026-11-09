
COMMAND_RISK_MAPPING = {

    # Read-only or harmless operations.
    # Argument, path and sensitive-file validation is still required.
    "low": [
        "BREAK",
        "CD",
        "CHDIR",
        "CLS",
        "COLOR",
        "COMP",
        "DIR",
        "DRIVERQUERY",
        "ECHO",
        "ENDLOCAL",
        "EXIT",
        "FC",
        "FIND",
        "FINDSTR",
        "GOTO",
        "GPRESULT",
        "HELP",
        "MORE",
        "PAUSE",
        "POPD",
        "PROMPT",
        "PUSHD",
        "REM",
        "SHIFT",
        "SORT",
        "SYSTEMINFO",
        "TASKLIST",
        "TITLE",
        "TREE",
        "TYPE",
        "VER",
        "VOL",
        "VERIFY",
    ],

    # Limited modifications or reversible operations.
    # Arguments may increase the risk.
    "medium": [
        "CHCP",
        "COMPACT",
        "LABEL",
        "MD",
        "MKDIR",
        "PRINT",
        "REN",
        "RENAME",
    ],

    # Significant modifications.
    # Require approval and strict argument validation.
    "high": [
        "ATTRIB",
        "CACLS",
        "COPY",
        "ICACLS",
        "MOVE",
        "SUBST",
        "XCOPY",
    ],

    # Potentially destructive operations.
    # Require explicit approval and strict path validation.
    "destructive": [
        "CONVERT",
        "DEL",
        "ERASE",
        "RD",
        "RECOVER",
        "REPLACE",
        "RMDIR",
        "ROBOCOPY",
    ],

    # Never exposed through the general command interface.
    # Unknown commands also default to blocked.
    "blocked": [
        "ASSOC",
        "BCDEDIT",
        "CALL",
        "CHKDSK",
        "CHKNTFS",
        "CMD",
        "DATE",
        "DISKPART",
        "DOSKEY",
        "FOR",
        "FORMAT",
        "FSUTIL",
        "FTYPE",
        "GRAFTABL",
        "IF",
        "MKLINK",
        "MODE",
        "OPENFILES",
        "PATH",
        "POWERSHELL",
        "PWSH",
        "REG",
        "NET",
        "CERTUTIL",
        "SC",
        "SCHTASKS",
        "SET",
        "SETLOCAL",
        "SHUTDOWN",
        "START",
        "TIME",
        "WMIC",
        "WSL",
    ],
}
