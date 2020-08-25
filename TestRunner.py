import numpy as np
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

        self.ansys.finish()
        self.ansys.run("/CLEAR")

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
        self.ansys.run("/PREP7")

        pair_sets = self.find_node_pairs(dimensions)

        rn = self.retained_nodes
        with self.ansys.non_interactive:
            for i, pair_set in enumerate(pair_sets):
                for pair in pair_set:
                    if rn[0] in pair:
                        continue

                    for ax in ["UX", "UY", "UZ"]:
                        # com = [
                        #     f"CE,NEXT,0,{pair[0]},{ax},1,{pair[1]},{ax},-1,{rnx},{ax},-1",
                        #     "CE,HIGH,0,{rn[0]},{ax},1",
                        # ]
                        # print(com)
                        # (self.ansys.run(chunk) for chunk in com)
                        # fmt: off
                        self.ansys.ce("NEXT",0,   # ansys.ce only has 3 terms implemented
                            node1=pair[0], lab1=ax, c1=1,
                            node2=pair[1], lab2=ax, c2=-1,
                            node3=rn[i+1], lab3=ax, c3=-1
                        )
                        self.ansys.ce("HIGH",0,
                            node1=rn[0], lab1=ax, c1=1,
                        )
                        # fmt: on
        pass

    @logger_wraps()
    def find_node_pairs(self, dimensions):
        pair_sets = []

        for i, axis in enumerate(AXES):  # Select exterior nodes on each axis
            self.ansys.nsel("S", "LOC", axis, dimensions.side_length / 2)
            self.ansys.nsel("A", "LOC", axis, -dimensions.side_length / 2)

            # Get coordinates and number in one row
            face_nodes = np.hstack(
                (
                    self.ansys.mesh.nodes,
                    np.reshape(self.ansys.mesh.nnum, (len(self.ansys.mesh.nnum), 1)),
                )
            )

            # Sort coordinates so duplicates will be adjacent
            face_nodes = face_nodes[
                np.lexsort(
                    (
                        -face_nodes[:, i],
                        face_nodes[:, (i + 1) % 3],
                        face_nodes[:, (i + 2) % 3],
                    )
                )
            ]

            # Extract every pair of node numbers
            pair_sets.append(
                np.stack((face_nodes[::2, -1], face_nodes[1::2, -1])).astype(int).T
            )

        return pair_sets

    @logger_wraps()
    def generate_load_steps(self, loads):
        if loads.kind != "displacement":
            raise NotImplementedError

        self.ansys.run("/SOLU")

        for i in range(1, 4):  # Normal cases
            self.ansys.lsclear("ALL")

            for j, n in enumerate(self.retained_nodes):
                # (self.ansys.d(n, axis) for axis in NORMAL_FIXED_AXES[j])  # Commands don't execute?
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
        self.ansys.run("/SOLU")
        with self.ansys.non_interactive:
            self.ansys.lssolve(1, 6)

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
        self.retained_nodes.extend(self.ansys.mesh.nnum)
        self.ansys.nsel("S", "LOC", "X", dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Y", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Z", -dimensions.side_length / 2)
        self.retained_nodes.extend(self.ansys.mesh.nnum)
        self.ansys.nsel("S", "LOC", "X", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Y", dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Z", -dimensions.side_length / 2)
        self.retained_nodes.extend(self.ansys.mesh.nnum)
        self.ansys.nsel("S", "LOC", "X", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Y", -dimensions.side_length / 2)
        self.ansys.nsel("R", "LOC", "Z", dimensions.side_length / 2)
        self.retained_nodes.extend(self.ansys.mesh.nnum)

        self.ansys.allsel()
        return self.retained_nodes  # for logging purposes

    @logger_wraps()
    def load_parameters(self):
        try:
            self.ansys.load_parameters()
            self.parameters = self.ansys.parameters
        except:
            raise Exception("Unable to load Ansys parameters")
