"""Test paketi. ollama_asistan/ dizinini import yoluna ekler ki testler
`import tools`, `import ollama_client`, `import chat` yapabilsin.

Testler DETERMINISTIKTIR: hicbiri calisan Ollama'ya ya da canli internet/hava
API'sine bagli degildir; HTTP katmani mock'lanir. Canli model degerlendirmesi
ayridir: tests/eval/run_eval.py (Ollama gerektirir).
"""

import os
import sys

_APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ollama_asistan")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)
