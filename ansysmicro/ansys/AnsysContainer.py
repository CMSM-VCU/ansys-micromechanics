from pathlib import Path

import ansys.mapdl.core
from ansys.mapdl.core import launch_mapdl
from loguru import logger


class AnsysContainer:
    def __init__(self, launch_options: dict = dict()):
        self.launch_options = launch_options

    def __enter__(self):
        # TODO: Add exception handling for lock file conflict
        if "run_location" in self.launch_options:
            Path(self.launch_options["run_location"]).mkdir(parents=True, exist_ok=True)
        self.ansys = launch_mapdl(**self.launch_options)

        setattr(self.ansys, "pymapdl_version", ansys.mapdl.core.__version__)
        logger.debug(self.ansys)
        return self.ansys

    def __exit__(self, type, value, traceback):
        """Ensure that Ansys instance is closed when done using class."""
        logger.info("Attempting to exit Ansys...")
        self.ansys.exit()
        logger.info("Exited successfully")
