from typing import List, Sequence, Tuple

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
        self.lengths = np.diff(testrunner.mesh_extents(), axis=1).T[0]

        self.loading = testrunner.test_case.loading
        self.tensors = LoadingHandler.prepare_loading_tensors(self.loading)

    @staticmethod
    def prepare_loading_tensors(
        loading_data: RecursiveNamespace, domain_size: Sequence[float] = None
    ) -> Tuple[np.ndarray]:
        """Take user input loading parameters and convert to sequence of strain*
        tensors, one for each load case.

        Args:
            loading_data (RecursiveNamespace): Object containing loading data as
                attributes. Available attributes depend on loading_data.kind parameter.
            domain_size (Sequence[float], optional): Side lengths of domain, assuming
                rectangular prism. len=3. Defaults to None.
                - Note: This argument is required when loading_data.kind=="displacement"

        Raises:
            Exception: domain_size missing when loading_data.kind=="displacement"

        Returns:
            Tuple[np.ndarray]: Tuple containing one (3,3) array for each load case.
        """
        if loading_data.kind == "displacement":
            assert (
                domain_size is not None
            ), "Domain size is required for displacement loading kind."

            tensors = tuple(
                LoadingHandler.convert_directions_to_strain_tensors(
                    loading_data.directions,
                    loading_data.normalMagnitude,
                    loading_data.shearMagnitude,
                    domain_size,
                )
            )
        elif loading_data.kind == "tensor":
            mag = loading_data.magnitudeMultiplier
            tensors = tuple(
                [
                    [elem * mag if elem is not None else None for elem in row]
                    for row in tensor
                ]
                for tensor in loading_data.tensors
            )
        else:
            raise Exception(f"Invalid loading kind: {loading_data.kind}")

        return tensors

    @staticmethod
    def convert_directions_to_strain_tensors(
        directions: Sequence[str],
        normal_mag: float,
        shear_mag: float,
        lengths: Sequence[float],
    ) -> List[np.ndarray]:
        """Produce list of strain* tensors according to list of loading directions,
        two magnitudes, and domain side lengths. See convert_direction_to_strain_tensor
        for details.

        Args:
            directions (Sequence[str]): List of direction strings
            normal_mag (float): Displacement magnitude for normal loading cases
            shear_mag (float): Displacement magnitude for shear loading cases
            lengths (Sequence): Side lengths of domain

        Returns:
            List[np.ndarray]: List of (3,3) arrays containing strain* tensors.
        """
        return [
            LoadingHandler.convert_direction_to_strain_tensor(
                direction, normal_mag, shear_mag, lengths
            )
            for direction in directions
        ]

    @staticmethod
    def convert_direction_to_strain_tensor(
        direction: str, normal_mag: float, shear_mag: float, lengths: Sequence[float]
    ) -> np.ndarray:
        """Produce strain* tensor according to loading direction/planes, a displacement
        magnitude for normal and shear loading, and the side lengths of the rectangular
        prismatic domain.

        Note: A value of None in the strain* tensor indicates a traction-free boundary
        condition or unprescribed strain value.

        Args:
            direction (str): String giving uniaxial loading direction. Must obey the
            regex: ^-?[123][123]$ , such as "11", "-13", "32".
            normal_mag (float): Displacement magnitude if direction is normal (i==j)
            shear_mag (float): Displacement magnitude if direction is shear (i!=j)
            lengths (Sequence[float]): Side lengths of domain, used to convert to strain

        Returns:
            np.ndarray: (3,3) array containing corresponding strain* tensor.
        """
        base = ([0, 0, 0], [0, 0, 0], [0, 0, 0])
        sign = -1 if len(direction) == 3 else 1
        i, j = list(map(lambda x: int(x) - 1, direction[-2:]))

        mag = normal_mag if i == j else shear_mag
        mag = mag / lengths[i]

        tensor = list(base)
        tensor[i][j] = sign * mag

        if i == j:
            tensor[(i + 1) % 3][(i + 1) % 3] = None
            tensor[(i + 2) % 3][(i + 2) % 3] = None

        return tensor

    def apply_strain_tensor(self, tensor: np.ndarray) -> None:
        """Apply a strain* tensor as displacement constraints on the retained nodes of
        an RVE using Ansys.

        Args:
            tensor (np.ndarray): (3,3) array containing strain* values
        """
        self.ansys.run("/SOLU")
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
