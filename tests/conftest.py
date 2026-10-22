"""Os testes nunca leem nem gravam presets na pasta do usuário."""
from __future__ import annotations

import os
import tempfile

os.environ["PIXEL_ATELIER_ESTILOS"] = tempfile.mkdtemp(prefix="pixel-atelier-presets-")
