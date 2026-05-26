#!/bin/bash
pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=/opt/render/.cache/ms-playwright playwright install chromium