@echo off
echo Сборка EXE-файла Sticker Frame Generator...

REM Очистка предыдущих сборок
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM Сборка с учетом всех зависимостей
pyinstaller --onefile --windowed ^
  --name "StickerFrameGenerator" ^
  --hidden-import=PIL ^
  --hidden-import=PyQt6 ^
  --hidden-import=PyQt6.QtCore ^
  --hidden-import=PyQt6.QtGui ^
  --hidden-import=PyQt6.QtWidgets ^
  --add-data "test_stickers;test_stickers" ^
  sticker_frame_gui.py

if exist "dist\StickerFrameGenerator.exe" (
  echo Сборка успешно завершена!
  echo EXE-файл находится в папке: dist\StickerFrameGenerator.exe
  pause
) else (
  echo Ошибка при сборке!
  pause
)