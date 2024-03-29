from pathlib import Path

import ansys.mapdl.core
from ansys.mapdl.core import launch_mapdl


class AnsysContainer:
    def __init__(self, launch_options=None):
        self.launch_options = launch_options

    def __enter__(self):
        # TODO: Add exception handling for lock file conflict
        if isinstance(self.launch_options, dict):
            if "run_location" in self.launch_options:
                Path(self.launch_options["run_location"]).mkdir(
                    parents=True, exist_ok=True
                )
            self.ansys = launch_mapdl(**self.launch_options)
        else:
            self.ansys = launch_mapdl()

        setattr(self.ansys, "pymapdl_version", ansys.mapdl.core.__version__)
        print(self.ansys)
        return self.ansys

    def __exit__(self, type, value, traceback):
        """Ensure that Ansys instance is closed when done using class.
        """
        print("Attempting to exit Ansys...")
        self.ansys.exit()
        print("Exited successfully")
