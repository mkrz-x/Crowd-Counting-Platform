#!/usr/bin/env python3
"""
Test script to check OpenCV installation
"""
import sys

try:
    import cv2
    print("✅ OpenCV imported successfully!")
    print(f"OpenCV version: {cv2.__version__}")
    print("OpenCV build info:")
    print(cv2.getBuildInformation())
except ImportError as e:
    print(f"❌ Failed to import OpenCV: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error with OpenCV: {e}")
    sys.exit(1)