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

        self.loading = testrunner.test_case.loading

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
