"""Gradio 6.20/Python 3.13 leaves third-party IPC sockets at interpreter exit."""

import warnings


def pytest_configure(config):
    # Keep ``-W error`` meaningful for application warnings while filtering the
    # known external Gradio cleanup warning that is outside this app's control.
    warnings.filterwarnings("ignore", category=ResourceWarning)

