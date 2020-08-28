from typing import List, Any
import numpy as np
import pyansys

from utils import logger_wraps, decorate_all_methods
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

DECIMAL_PLACES = 5


@decorate_all_methods(logger_wraps)
class TestRunner:
    ansys: Any  #: pyansys.mapdl_corba.MapdlCorba # don't know how to type hint this
    element_type: int
    launch_options: dict
    retained_nodes: List

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

    def prepare_mesh(self, dimensions, materials, arrangement):
        self.generate_base_mesh(dimensions)
        self.get_retained_nodes(dimensions)
        self.define_materials(materials)
        self.assign_element_materials(arrangement)
        self.apply_periodic_conditions(dimensions)

    def run_test_sequence(self, loads):
        for load_case in range(1, 7):
            self.ansys.ddele("ALL")  # Will need to change for any other loading methods
            if load_case < 4:
                self.apply_loading_normal(load_case, loads)
            elif load_case >= 4:
                self.apply_loading_shear(load_case - 3, loads)

            self.solve()
            self.debug_stat()
            self.extract_raw_results()

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

    def get_retained_nodes(self, dimensions):
        coord_signs = [[-1, -1, -1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]
        magnitude = dimensions.side_length / 2

        node_coords = [[sign * magnitude for sign in node] for node in coord_signs]

        self.retained_nodes = []

        for node in node_coords:
            self.retained_nodes.append(self.get_node_num_at_loc(*node))

        return self.retained_nodes  # for logging purposes

    def get_node_num_at_loc(self, x, y, z):
        # WARNING: This uses the Ansys inline node() function, which returns whichever
        # node is CLOSEST to the location.
        inline = f"node({x},{y},{z})"
        self.ansys.run("NODE_NUMBER_TEMP=" + inline)
        if pyansys.__version__[:4] == "0.43":
            return int(self.ansys.parameters["node_number_temp"])
        else:
            self.load_parameters()
            return int(self.parameters["NODE_NUMBER_TEMP"])

    def select_node_at_loc(self, x, y, z, kind="S"):
        nnum = self.get_node_num_at_loc(x, y, z)
        if kind:
            self.ansys.nsel(kind, "NODE", "", nnum)

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

    def apply_periodic_conditions(self, dimensions):
        self.ansys.run("/PREP7")

        pair_sets = self.find_node_pairs(dimensions)

        rn = self.retained_nodes

        if pyansys.__version__[:4] == "0.43":
            context = self.ansys.chain_commands
        else:
            context = self.ansys.non_interactive

        for i, pair_set in enumerate(pair_sets):
            with context:
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

    def find_node_pairs(self, dimensions):
        pair_sets = []

        for i, axis in enumerate(AXES):  # Select exterior nodes on each axis
            self.ansys.nsel("S", "LOC", axis, dimensions.side_length / 2)

            if pyansys.__version__[:4] == "0.43":
                nodes_pos = np.around(self.ansys.mesh.nodes, DECIMAL_PLACES)
                nnum_pos = self.ansys.mesh.nnum
            else:
                nodes_pos = np.around(self.ansys.nodes, DECIMAL_PLACES)
                nnum_pos = self.ansys.nnum

            self.ansys.nsel("S", "LOC", axis, -dimensions.side_length / 2)

            if pyansys.__version__[:4] == "0.43":
                nodes_neg = np.around(self.ansys.mesh.nodes, DECIMAL_PLACES)
                nnum_neg = self.ansys.mesh.nnum
            else:
                nodes_neg = np.around(self.ansys.nodes, DECIMAL_PLACES)
                nnum_neg = self.ansys.nnum

            # Delete coordinate along current axis
            nodes_pos = np.delete(nodes_pos, i, 1)
            nodes_neg = np.delete(nodes_neg, i, 1)

            # Get coordinates and number in one row
            face_nodes_pos = np.hstack(
                (nodes_pos, np.reshape(nnum_pos, (len(nnum_pos), 1)),)
            )
            face_nodes_neg = np.hstack(
                (nodes_neg, np.reshape(nnum_neg, (len(nnum_neg), 1)),)
            )

            # Sort coordinates so counterparts will be at same index
            face_nodes_pos = face_nodes_pos[
                np.lexsort((face_nodes_pos[:, 0], face_nodes_pos[:, 1],))
            ]
            face_nodes_neg = face_nodes_neg[
                np.lexsort((face_nodes_neg[:, 0], face_nodes_neg[:, 1],))
            ]

            # Extract every pair of node numbers
            pair_sets.append(
                np.stack((face_nodes_pos[:, -1], face_nodes_neg[:, -1])).astype(int).T
            )

        self.ansys.allsel()

        return pair_sets

    def apply_loading_normal(self, axis, loads):
        for j, n in enumerate(self.retained_nodes):
            for axis_label in NORMAL_FIXED_AXES[j]:
                self.ansys.d(n, axis_label)

        self.ansys.d(
            self.retained_nodes[axis], "U" + AXES[axis - 1], loads.normal_magnitude
        )

    def apply_loading_shear(self, axis, loads):
        for j, n in enumerate(self.retained_nodes):
            for axis_label in SHEAR_FIXED_AXES[j]:
                self.ansys.d(n, axis_label)

        self.ansys.d(
            self.retained_nodes[axis], "U" + AXES[axis % 3], loads.shear_magnitude
        )

        # How do I verify that load steps were input correctly? How do I access the
        # load steps from self.ansys?

    def solve(self):
        self.ansys.run("/SOLU")
        self.ansys.allsel()
        self.ansys.solve()

    def extract_raw_results(self):
        pass

    def calculate_properties(self):
        properties = Material(99, [1], [1], [1])
        return properties

    def load_parameters(self):
        try:
            self.ansys.load_parameters()
            self.parameters = self.ansys.parameters
        except:
            raise Exception("Unable to load Ansys parameters")

    def debug_stat(self):
        self.ansys.lsoper()
        self.ansys.stat()
        self.ansys.fecons()
        self.ansys.stat()
        self.ansys.ceqn()
        self.ansys.stat()
