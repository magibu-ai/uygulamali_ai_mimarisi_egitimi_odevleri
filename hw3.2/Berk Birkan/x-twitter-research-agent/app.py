import os
import sys
from pathlib import Path

import spaces

sys.path.insert(0, str(Path(__file__).parent / "src"))

from x_research_agent.ui.app import build_app  # noqa: E402

demo = build_app()


@spaces.GPU(duration=1)
def zerogpu_healthcheck() -> str:
    """Declare ZeroGPU compatibility without using GPU for normal research calls."""
    return "ready"


if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "7860")))
    demo.queue(default_concurrency_limit=8).launch(server_name="0.0.0.0", server_port=port)
