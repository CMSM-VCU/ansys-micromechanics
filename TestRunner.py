import pyansys

from tuples import Material


class TestRunner:
    def __init__(self, launch_options=None):
        """Launches an Ansys instance. See pyansys documentation for launch options such
        as job directory and executable path.

        Args:
            launch_options (dict, optional): dictionary of keyword arguments for pyansys.launch_mapdl()
        """
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

    def generate_base_mesh(self, dimensions):
        """Generate uniform cubic mesh according to overall side length and element edge
        length. Assumes a cube centered around (0,0,0).

        Args:
            dimensions (Dims): tuple containing side length and element length
        """
        print("generate_base_mesh")
        pass

    def define_materials(self, materials):
        print("define_materials", materials)
        pass

    def apply_periodic_conditions(self):
        print("apply_periodic_conditions")
        pass

    def generate_load_steps(self, loads):
        print("generate_load_steps", loads)
        pass

    def assign_element_materials(self, arrangement):
        print("assign_element_materials", arrangement)
        pass

    def solve_load_steps(self):
        print("solve_load_steps")
        pass

    def extract_raw_results(self):
        print("extract_raw_results")
        pass

    def calculate_properties(self):
        properties = Material(99, [1], [1], [1])
        print("calculate_properties", properties)
        return properties

    def load_parameters(self):
        try:
            self.ansys.load_parameters()
            self.parameters = self.ansys.parameters
        except:
            raise Exception("Unable to load Ansys parameters")
