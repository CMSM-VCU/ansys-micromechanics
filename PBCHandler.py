import numpy as np
from numpy.core import test

from utils import round_to_sigfigs

AXES = ["X", "Y", "Z"]
SIG_FIGS = 10


class PBCHandler:
    def __init__(self, testrunner):
        self.ansys = testrunner.ansys
        self.retained_nodes = testrunner.retained_nodes
        self.mesh_extents = testrunner.mesh_extents

    def apply_periodic_conditions(self):
        self.ansys.run("/PREP7")

        pair_sets = self.find_node_pairs()

        rn = self.retained_nnum

        if self.ansys.pyansys_version[:4] == "0.43":
            context = self.ansys.chain_commands
        else:
            context = self.ansys.non_interactive

        for i, pair_set in enumerate(pair_sets):
            with context:
                for pair in pair_set:
                    if rn[0] in pair:
                        continue

                    for ax in ["UX", "UY", "UZ"]:
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

    def find_node_pairs(self):
        pair_sets = []

        for i, axis in enumerate(AXES):  # Select exterior nodes on each axis
            self.ansys.nsel("S", "LOC", axis, self.mesh_extents(allsel=True)[i, 1])

            if self.ansys.pyansys_version[:4] == "0.43":
                nodes_pos = self.round_to_sigfigs(self.ansys.mesh.nodes, SIG_FIGS)
                nnum_pos = self.ansys.mesh.nnum
            else:
                nodes_pos = self.round_to_sigfigs(self.ansys.nodes, SIG_FIGS)
                nnum_pos = self.ansys.nnum

            self.ansys.nsel("S", "LOC", axis, self.mesh_extents(allsel=True)[i, 0])

            if self.ansys.pyansys_version[:4] == "0.43":
                nodes_neg = self.round_to_sigfigs(self.ansys.mesh.nodes, SIG_FIGS)
                nnum_neg = self.ansys.mesh.nnum
            else:
                nodes_neg = self.round_to_sigfigs(self.ansys.nodes, SIG_FIGS)
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

            assert self.verify_equality(face_nodes_pos[:, :2], face_nodes_neg[:, :2])

            # Extract every pair of node numbers
            pair_sets.append(
                np.stack((face_nodes_pos[:, -1], face_nodes_neg[:, -1])).astype(int).T
            )

        self.ansys.allsel()

        return pair_sets

    def verify_equality(self, arr1, arr2):
        print(np.max(np.abs(arr1 - arr2)))
        if np.array_equal(arr1, arr2):
            return True
        bad_idx = np.argwhere(np.not_equal(arr1, arr2))
        bad_arr1 = arr1[bad_idx[:, 0]]
        bad_arr2 = arr2[bad_idx[:, 0]]
        diff = np.abs(bad_arr1 - bad_arr2)
        culprits = diff.argsort(axis=0)[-1]
        x_bad = (bad_arr1[culprits[0]], bad_arr2[culprits[0]])
        y_bad = (bad_arr1[culprits[1]], bad_arr2[culprits[1]])

        pass
