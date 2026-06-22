@echo off
echo =========================================
echo Building def executable with PyInstaller
echo =========================================
call .venv\Scripts\activate.bat
pyinstaller --clean def.spec

if %ERRORLEVEL% neq 0 (
    echo PyInstaller build failed!
    exit /b %ERRORLEVEL%
)

echo =========================================
echo Building Inno Setup Installer
echo =========================================
set "ISCC_USER_PATH=%USERPROFILE%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
set "ISCC_SYSTEM_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if exist "%ISCC_USER_PATH%" (
    "%ISCC_USER_PATH%" installer.iss
) else if exist "%ISCC_SYSTEM_PATH%" (
    "%ISCC_SYSTEM_PATH%" installer.iss
) else (
    iscc installer.iss
)

if %ERRORLEVEL% neq 0 (
    echo Inno Setup compilation failed!
    exit /b %ERRORLEVEL%
)

echo =========================================
echo Build and Installation package completed!
echo =========================================
