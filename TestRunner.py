import pyansys

from utils import logger_wraps
from tuples import Material

AXES = ["X", "Y", "Z"]

# Axes that will always be constrained for each retained node
NORMAL_FIXED_AXES = [["UX", "UY", "UZ"], ["UY", "UZ"], ["UX", "UZ"], ["UX", "UY"]]
SHEAR_FIXED_AXES = [
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
]


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
        self.ansys.run("/PREP7")
        e_str = ["EX", "EY", "EZ"]
        g_str = ["GXY", "GYZ", "GXZ"]
        pr_str = ["PRXY", "PRYZ", "PRXZ"]
        for material in materials:
            id = material.id
            for i in range(3):
                self.ansys.mp(e_str[i], id, material.elastic_moduli[i])
                self.ansys.mp(g_str[i], id, material.shear_moduli[i])
                self.ansys.mp(pr_str[i], id, material.poisson_ratios[i])
        # How do I verify that materials were input correctly? How do I access the
        # materials from self.ansys?

    @logger_wraps()
    def apply_periodic_conditions(self, dimensions):
        pass

    @logger_wraps()
    def generate_load_steps(self, loads):
        if loads.kind != "displacement":
            raise NotImplementedError

        self.ansys.run("/SOLU")

        for i in range(1, 4):  # Normal cases
            self.ansys.lsclear("ALL")

            for j, n in enumerate(self.retained_nodes):
                # (self.ansys.d(n, axis) for axis in NORMAL_FIXED_AXES[j])
                for axis in NORMAL_FIXED_AXES[j]:
                    self.ansys.d(n, axis)

            self.ansys.d(
                self.retained_nodes[i], "U" + AXES[i - 1], loads.normal_magnitude
            )

            self.ansys.lswrite(i)

        for i in range(1, 4):  # Shear cases
            self.ansys.lsclear("ALL")

            for j, n in enumerate(self.retained_nodes):
                # (self.ansys.d(n, axis) for axis in SHEAR_FIXED_AXES[j])
                for axis in SHEAR_FIXED_AXES[j]:
                    self.ansys.d(n, axis)

            self.ansys.d(
                self.retained_nodes[i], "U" + AXES[i % 3], loads.shear_magnitude
            )

            self.ansys.lswrite(i + 3)

        # How do I verify that materials were input correctly? How do I access the
        # materials from self.ansys?

    @logger_wraps()
    def assign_element_materials(self, arrangement):
        # This implementation is probably super slow
        # Individual emodif commands may be extra slow, so try adding to component
        # per material number, then emodif on each component
        self.ansys.run("/PREP7")
        for element in arrangement:
            self.ansys.esel("S", "CENT", "X", element[0])
            self.ansys.esel("R", "CENT", "Y", element[1])
            self.ansys.esel("R", "CENT", "Z", element[2])
            self.ansys.emodif("ALL", "MAT", element[3])

        self.ansys.allsel()

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
    def get_retained_nodes(self, dimensions):
        # Can this be cleaned up? Iterate over list of [1,-1,-1]-style multipliers?
        self.retained_nodes = []
        self.ansys.nsel("S", "LOC", "X", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Y", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Z", -dimensions.side_length / 2)
        self.retained_nodes.extend(self.ansys.nnum)
        self.ansys.nsel("S", "LOC", "X", dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Y", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Z", -dimensions.side_length / 2)
        self.retained_nodes.extend(self.ansys.nnum)
        self.ansys.nsel("S", "LOC", "X", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Y", dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Z", -dimensions.side_length / 2)
        self.retained_nodes.extend(self.ansys.nnum)
        self.ansys.nsel("S", "LOC", "X", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Y", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Z", dimensions.side_length / 2)
        self.retained_nodes.extend(self.ansys.nnum)

        self.ansys.allsel()
        return self.retained_nodes  # for logging purposes

    @logger_wraps()
    def load_parameters(self):
        try:
            self.ansys.load_parameters()
            self.parameters = self.ansys.parameters
        except:
            raise Exception("Unable to load Ansys parameters")
