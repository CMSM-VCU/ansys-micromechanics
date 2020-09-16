import numpy as np
from utils import decorate_all_methods, logger_wraps

AXES = ["X", "Y", "Z"]

# Axes that will always be constrained for each retained node
NORMAL_FIXED_AXES = [["UX", "UY", "UZ"], ["UY", "UZ"], ["UX", "UZ"], ["UX", "UY"]]
SHEAR_FIXED_AXES = [
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
    ["UX", "UY", "UZ"],
]


class LoadingHandler:
    def __init__(self, testrunner):
        self.ansys = testrunner.ansys
        self.retained_nodes = testrunner.retained_nodes
        self.lengths = np.diff(testrunner.mesh_extents(), axis=1).T[0]

        self.loading = testrunner.test_case.loading
        self.prepare_loading()

    def prepare_loading(self):
        if self.loading.kind == "displacement":
            self.tensors = tuple(
                self.convert_directions_to_strain_tensors(
                    self.loading.directions,
                    self.loading.normalMagnitude,
                    self.loading.shearMagnitude,
                    self.lengths,
                )
            )
        elif self.loading.kind == "tensor":
            self.tensors = (
                np.array(self.loading.tensors) * self.loading.magnitudeMultiplier
            ).tolist()
        print(self.tensors)
        pass

    @staticmethod
    def convert_directions_to_strain_tensors(
        directions, normal_mag, shear_mag, lengths
    ):
        return [
            LoadingHandler.convert_direction_to_strain_tensor(
                direction, normal_mag, shear_mag, lengths
            )
            for direction in directions
        ]

    @staticmethod
    def convert_direction_to_strain_tensor(direction, normal_mag, shear_mag, lengths):
        base = ([0, 0, 0], [0, 0, 0], [0, 0, 0])
        if len(direction) == 3:
            sign = -1
        else:
            sign = 1

        i, j = list(map(lambda x: int(x) - 1, direction[-2:]))

        if i == j:
            mag = normal_mag
        else:
            mag = shear_mag

        mag = mag / lengths[i]

        tensor = list(base)
        tensor[i][j] = sign * mag
        return tensor

    def apply_loading_normal(self, axis):
        for j, n in enumerate(self.retained_nodes):
            for axis_label in NORMAL_FIXED_AXES[j]:
                self.ansys.d(n, axis_label)

        self.ansys.d(
            self.retained_nodes[axis],
            "U" + AXES[axis - 1],
            self.loading.normalMagnitude,
        )

    def apply_loading_shear(self, axis):
        for j, n in enumerate(self.retained_nodes):
            for axis_label in SHEAR_FIXED_AXES[j]:
                self.ansys.d(n, axis_label)

        self.ansys.d(
            self.retained_nodes[axis],
            "U" + AXES[axis % 3],
            self.loading.shearMagnitude,
        )

        # How do I verify that load steps were input correctly? How do I access the
        # load steps from self.ansys?
