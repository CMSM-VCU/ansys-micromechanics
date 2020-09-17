from typing import Sequence, Tuple
import numpy as np
from numpy.core import test

from utils import round_to_sigfigs
from utils import decorate_all_methods, logger_wraps

AXES = ["X", "Y", "Z"]
SIG_FIGS = 8
EPSILON = np.finfo(float).eps * 1e3  # Should be ~1e-13
TOLERANCE_MULT = 1e-6


@decorate_all_methods(logger_wraps)
class PBCHandler:
    """Handle the preparation and application of periodic boundary conditions for an
    Ansys RVE test sequence. The ResultsHandler instance is paired with a TestRunner
    instance on initialization.
    """

    def __init__(self, testrunner):
        self.ansys = testrunner.ansys
        self.retained_nodes = testrunner.retained_nodes
        self.mesh_extents = testrunner.mesh_extents()

    def apply_periodic_conditions(self):
        self.ansys.run("/PREP7")

        pair_sets = self.find_node_pairs(self.mesh_extents)

        rn = self.retained_nodes

        print("Applying periodic BCs to face set ", end="")
        for i, pair_set in enumerate(pair_sets):
            print("i... ", end="")
            # with self.ansys.chain_commands:
            with self.ansys.non_interactive:
                for pair in pair_set:
                    if rn[0] in pair:
                        continue

                    for ax in ["UX", "UY", "UZ"]:
                        # fmt: off
                        self.ansys.ce("NEXT",0,   # ansys.ce can only take 3 terms
                            node1=pair[0], lab1=ax, c1=1,
                            node2=pair[1], lab2=ax, c2=-1,
                            node3=rn[i+1], lab3=ax, c3=-1
                        )
                        self.ansys.ce("HIGH",0,
                            node1=rn[0], lab1=ax, c1=1,
                        )
                        # fmt: on
        pass
        # Can I get the number of constraint equations to use as a return value?

    def find_node_pairs(self, mesh_extents: np.ndarray) -> Sequence[np.ndarray]:
        pair_sets = []

        tolerances = (np.diff(mesh_extents) * TOLERANCE_MULT).flatten()

        for axis_ind, axis in enumerate(AXES):  # Select exterior nodes on each axis
            nodes_pos, nnum_pos, nodes_neg, nnum_neg = self.get_opposite_face_nodes(
                axis, mesh_extents[axis_ind], tolerances[axis_ind]
            )

            nodes_pos = PBCHandler.clean_node_coords(nodes_pos, axis_ind)
            face_nodes_pos = PBCHandler.sort_2d_with_index(nodes_pos, nnum_pos)

            nodes_neg = PBCHandler.clean_node_coords(nodes_neg, axis_ind)
            face_nodes_neg = PBCHandler.sort_2d_with_index(nodes_neg, nnum_neg)

            assert PBCHandler.verify_equality(
                face_nodes_pos[:, :2], face_nodes_neg[:, :2]
            )

            # Extract every pair of node numbers
            pair_sets.append(
                np.stack((face_nodes_pos[:, -1], face_nodes_neg[:, -1])).astype(int).T
            )

        return pair_sets

    @staticmethod
    def sort_2d_with_index(nodes: np.ndarray, node_nums: np.ndarray) -> np.ndarray:
        nodes_combined = np.hstack([nodes, node_nums])
        return nodes_combined[np.lexsort(np.transpose(nodes))]

    @staticmethod
    def clean_node_coords(nodes: np.ndarray, axis_index: int) -> np.ndarray:
        # Delete coordinates column for current axis
        nodes = np.delete(nodes, axis_index, axis=1)
        # Replace values near zero with exactly zero
        nodes = np.where(np.abs(nodes) > EPSILON, nodes, 0.0)
        return nodes

    def get_opposite_face_nodes(
        self, axis: str, axis_extents: Sequence[float], tolerance: float = ""
    ) -> Tuple[np.ndarray]:
        self.ansys.seltol(tolerance)

        self.ansys.nsel("S", "LOC", axis, axis_extents[1])

        nodes_pos = round_to_sigfigs(self.ansys.mesh.nodes, SIG_FIGS)
        nnum_pos = np.reshape(self.ansys.mesh.nnum, (-1, 1))

        self.ansys.nsel("S", "LOC", axis, axis_extents[0])

        nodes_neg = round_to_sigfigs(self.ansys.mesh.nodes, SIG_FIGS)
        nnum_neg = np.reshape(self.ansys.mesh.nnum, (-1, 1))

        assert nodes_pos.shape == nodes_neg.shape, (
            f"Different number of nodes selected on opposite faces: "
            + f"{nodes_pos.shape=}, {nodes_neg.shape=}"
        )

        self.ansys.seltol()
        self.ansys.allsel()
        return nodes_pos, nnum_pos, nodes_neg, nnum_neg

    @staticmethod
    def verify_equality(arr1, arr2):
        if np.array_equal(arr1, arr2):
            return True

        # Identify bad elements for debugging
        print(np.max(np.abs(arr1 - arr2)))
        bad_idx = np.argwhere(np.not_equal(arr1, arr2))
        bad_arr1 = arr1[bad_idx[:, 0]]
        bad_arr2 = arr2[bad_idx[:, 0]]
        diff = np.abs(bad_arr1 - bad_arr2)
        culprits = diff.argsort(axis=0)[-1]
        x_bad = (bad_arr1[culprits[0]], bad_arr2[culprits[0]])
        y_bad = (bad_arr1[culprits[1]], bad_arr2[culprits[1]])
        print(x_bad, y_bad)

        pass
