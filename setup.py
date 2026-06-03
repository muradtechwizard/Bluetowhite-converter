from setuptools import setup
import os

APP = ['main.py']
DATA_FILES = []

OPTIONS = {
    'argv_emulation': True,
    # Remove or comment out the iconfile line
    # 'iconfile': 'app_icon.icns',  
    'plist': {
        'CFBundleName': "BlueWhiteConverter",
        'CFBundleDisplayName': "Blue & White Converter",
        'CFBundleGetInfoString': "Converts documents to Blue/White theme",
        'CFBundleIdentifier': "com.bluewhite.converter",
        'CFBundleVersion': "1.0.0",
        'CFBundleShortVersionString': "1.0.0",
        'NSHumanReadableCopyright': "© 2024 BlueWhite Converter"
    },
    'packages': ['PIL', 'pytesseract', 'pdf2image', 'img2pdf', 'docx2pdf'],
    'includes': ['PyQt6'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
