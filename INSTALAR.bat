@echo off
setlocal
cd /d "%~dp0"
title Claro One - Instalacao

echo ========================================
echo CLARO ONE - PRIMEIRA INSTALACAO
echo ========================================

if exist ".venv\Scripts\python.exe" goto install_packages

where py >nul 2>nul
if not errorlevel 1 (
  py -3 --version >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    goto create_venv
  )
)

where python >nul 2>nul
if not errorlevel 1 (
  python --version >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto create_venv
  )
)

echo ERRO: Python nao foi encontrado.
echo Instale o Python em https://www.python.org/downloads/windows/
echo Marque a opcao "Add Python to PATH" durante a instalacao.
goto failed

:create_venv
echo Criando o ambiente do projeto...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto failed

:install_packages
echo Instalando as dependencias. Aguarde...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Arquivo .env criado. Agora adicione sua GROQ_API_KEY nele.
) else (
  echo O arquivo .env existente foi preservado.
)

echo.
echo INSTALACAO CONCLUIDA COM SUCESSO.
echo Leia LEIA_PRIMEIRO.txt antes de iniciar.
pause
exit /b 0

:failed
echo.
echo A instalacao nao foi concluida. Revise a mensagem acima.
pause
exit /b 1
