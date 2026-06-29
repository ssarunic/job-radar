import sys
from pathlib import Path

# make `import app` (webapp/backend/app.py) resolvable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
