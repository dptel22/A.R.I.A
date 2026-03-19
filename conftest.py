import sys
from unittest.mock import MagicMock

sys.modules["numpy"] = MagicMock()
sys.modules["ultralytics"] = MagicMock()
sys.modules["ultralytics.engine.results"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.lib.enums"] = MagicMock()
sys.modules["reportlab.lib.units"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.ImageDraw"] = MagicMock()
sys.modules["PIL.ImageFont"] = MagicMock()
