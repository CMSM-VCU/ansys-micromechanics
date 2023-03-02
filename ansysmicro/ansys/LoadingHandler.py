import numpy as np

from ansysmicro.RecursiveNamespace import RecursiveNamespace
from ansysmicro.utils import decorate_all_methods, logger_wraps

DISP_AXES = ["UX", "UY", "UZ"]


@decorate_all_methods(logger_wraps)
class LoadingHandler:
    """Handler for processing loading input from user and applying specified loads to
    Ansys RVE test sequence. The LoadingHandler instance is paired with a TestRunner
    instance on initialization.

    *Note about strain tensors - What is referred to here as a strain tensor is actually
    the displacement gradient tensor.
    """

    def __init__(self, testrunner):
        self.ansys = testrunner.ansys
        self.retained_nodes = testrunner.retained_nodes
        self.lengths = np.diff(testrunner.mesh_extents, axis=1).T[0]

        self.loading = testrunner.test_case.loading
        self.tensors = LoadingHandler.prepare_loading_tensors(self.loading)

    @staticmethod
    def prepare_loading_tensors(loading_data: RecursiveNamespace) -> tuple[np.ndarray]:
        """Take user input loading parameters and convert to sequence of strain*
        tensors, one for each load case.

        Args:
            loading_data (RecursiveNamespace): Object containing loading data as
                attributes. Available attributes depend on loading_data.kind parameter.

        Returns:
            Tuple[np.ndarray]: Tuple containing one (3,3) array for each load case.
        """
        mag = loading_data.magnitudeMultiplier
        return tuple(
            [
                [elem * mag if elem is not None else None for elem in row]
                for row in tensor
            ]
            for tensor in loading_data.tensors
        )

    def apply_strain_tensor(self, tensor: np.ndarray) -> None:
        """Apply a strain* tensor as displacement constraints on the retained nodes of
        an RVE using Ansys.

        Args:
            tensor (np.ndarray): (3,3) array containing strain* values
        """
        self.ansys.slashsolu()
        self.ansys.allsel()
        self.ansys.ddele("ALL")

        for i, row in enumerate(tensor):
            for axis, strain in zip(DISP_AXES, row):
                if strain is None:
                    continue

                self.ansys.d(self.retained_nodes[i + 1], axis, strain * self.lengths[i])

        self.ansys.d(self.retained_nodes[0], "ALL", 0)

        # How do I verify that load steps were input correctly? How do I access the
        # load steps from self.ansys?
