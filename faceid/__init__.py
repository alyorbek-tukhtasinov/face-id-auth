"""FaceID Next — lokal, yangi avlod yuz orqali autentifikatsiya tizimi."""

import os as _os

__version__ = "2.0.0"

# Uchinchi tomon kutubxonalarining ortiqcha loglari
_os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
_os.environ.setdefault("GLOG_minloglevel", "2")
