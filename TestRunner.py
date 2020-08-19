import pyansys

from utils import logger_wraps
from tuples import Material


class TestRunner:
    def __init__(self, element_type=185, launch_options=None):
        """Launches an Ansys instance. See pyansys documentation for launch options such
        as job directory and executable path.

        Args:
            launch_options (dict, optional): dictionary of keyword arguments for pyansys.launch_mapdl()
        """
        self.element_type = element_type
        self.launch_options = launch_options

    def __enter__(self):
        # TODO: Add exception handling for lock file conflict
        if isinstance(self.launch_options, dict):
            self.ansys = pyansys.launch_mapdl(**self.launch_options)
        else:
            self.ansys = pyansys.launch_mapdl()
        return self

    def __exit__(self, type, value, traceback):
        """Ensure that Ansys instance is closed when done using class.
        """
        print("Attempting to exit Ansys...")
        self.ansys.exit()
        print("Exited successfully")
        # Add check to see if closed successfully?

    @logger_wraps()
    def generate_base_mesh(self, dimensions):
        """Generate uniform cubic mesh according to overall side length and element edge
        length. Assumes a cube centered around (0,0,0).

        Args:
            dimensions (Dims): tuple containing side length and element length
        """
        print("generate_base_mesh")
        half_side = dimensions.side_length / 2
        self.ansys.run("/PREP7")
        self.ansys.block(
            -half_side, half_side, -half_side, half_side, -half_side, half_side,
        )

        self.ansys.et(1, self.element_type)
        self.ansys.lesize("ALL", dimensions.element_length)
        self.ansys.mshkey(1)
        self.ansys.vmesh("ALL")
        # print(self.ansys.elements)

    @logger_wraps()
    def define_materials(self, materials):
        pass

    @logger_wraps()
    def apply_periodic_conditions(self):
        pass

    @logger_wraps()
    def generate_load_steps(self, loads):
        pass

    @logger_wraps()
    def assign_element_materials(self, arrangement):
        pass

    @logger_wraps()
    def solve_load_steps(self):
        pass

    @logger_wraps()
    def extract_raw_results(self):
        pass

    @logger_wraps()
    def calculate_properties(self):
        properties = Material(99, [1], [1], [1])
        return properties

    @logger_wraps()
    def load_parameters(self):
        try:
            self.ansys.load_parameters()
            self.parameters = self.ansys.parameters
        except:
            raise Exception("Unable to load Ansys parameters")
