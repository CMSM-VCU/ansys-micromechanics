from pathlib import Path
from typing import Any, List

import numpy as np

from ansysmicro.utils import decorate_all_methods, logger_wraps

from .AnsysContainer import AnsysContainer
from .LoadingHandler import LoadingHandler
from .PBCHandler import PBCHandler
from .ResultsHandler import ResultsHandler


@decorate_all_methods(logger_wraps)
class TestRunner:
    ansys: Any  #: pyansys.mapdl_corba.MapdlCorba # don't know how to type hint this
    launch_options: dict
    retained_nodes: List[int]
    retained_results: List[dict]

    def __init__(self, test_case, options=None):
        """See pyansys documentation for launch options such as job directory and executable path.

        Args:
            test_case (TestCase): TestCase object to which this TestRunner belongs
            options (dict, optional): dictionary of keyword arguments for pyansys.launch_mapdl()
        """
        self.test_case = test_case
        self.test_case.results = {}
        self.test_case.debug_results = {}
        self.launch_options = options
        try:
            self.jobname = options["jobname"]
        except:
            print("No jobname found. Defaulting to `file`")
            self.jobname = "file"
        try:
            self.jobdir = options["run_location"] + "\\"
        except:
            print("No jobdir found. Defaulting to `.\`")
            self.jobdir = ".\\"

    def run(self):
        """Execute the full test process. Launches and closes an Ansys instance.
        """
        with AnsysContainer(self.launch_options) as self.ansys:
            self.rst_path = Path(self.ansys._result_file)
            self.ansys.finish()
            self.ansys.run("/CLEAR")
            self.prepare_mesh()
            results = self.run_test_sequence()
        return results

    def prepare_mesh(self):
        """Execute the meshing and problem setup. These are the parts that do not change
        with load cases.
        """
        if self.test_case.mesh_type == "centroid":
            self.generate_base_mesh(**self.test_case.mesh)
            self.assign_element_materials()
        elif self.test_case.mesh_type == "external":
            self.load_external_mesh(**self.test_case.mesh)
        self.debug_stat()
        self.define_materials(self.test_case.materials)
        self.get_retained_nodes()
        self.pbc_handler = PBCHandler(self)
        self.pbc_handler.apply_periodic_conditions()

    def run_test_sequence(self):
        """Execute the load cases and process results.
        """
        self.results_handler = ResultsHandler(self)
        self.loading_handler = LoadingHandler(self)
        for load_case in np.arange(self.test_case.num_load_cases) + 1:
            self.results_handler.clear_results()
            self.load_case = load_case

            self.loading_handler.apply_strain_tensor(
                self.loading_handler.tensors[load_case - 1]
            )

            print(f"Beginning solve for {load_case=}")
            self.solve()
            print(f"Finished solve for {load_case=}")
            self.debug_stat()

            self.results_handler.extract_raw_results()
            self.results_handler.calculate_properties(load_case)

        return ResultsHandler.compile_results(
            results=self.results_handler.results,
            expected_property_sets=list(self.test_case.loading.expectedProperties),
            num_load_cases=self.test_case.num_load_cases,
            labels=self.test_case.loading.labels,
            debug_results=self.results_handler.debug_results,
        )  # expectedProperties passed in list() to pass copy, allowing mutation in function

    def load_external_mesh(
        self,
        elementType: str,
        nodeFileAbsolutePath: str,
        elementFileAbsolutePath: str,
        csysFileAbsolutePath: str = None,
        **kwargs,
    ):
        """Generate a mesh from a pair of preexisting node and element files, in Ansys
        NWRITE/NREAD and EWRITE/EREAD format.

        Args:
            elementType (str): Ansys element type used in this mesh
            nodeFileAbsolutePath (str): absolute path to file containing node data
            elementFileAbsolutePath (str): absolute path to file containing element data

        Returns:
            tuple(int, int): tuple containing number of nodes and elements in loaded mesh
        """
        self.ansys.run("/prep7")
        self.ansys.et(1, elementType)
        try:
            self.ansys.nread(nodeFileAbsolutePath)
            self.ansys.eread(elementFileAbsolutePath)
        except Exception as err:
            print(
                "Load failed. Likely caused by bad file name. ",
                "Attempting with symbolic links...",
            )
            self.load_mesh_with_symlinks(nodeFileAbsolutePath, elementFileAbsolutePath)

        assert self.ansys.mesh.n_node > 0, "No nodes loaded."
        assert self.ansys.mesh.n_elem > 0, "No elements loaded."

        if csysFileAbsolutePath:
            self.load_coordinate_systems(csysFileAbsolutePath)
        else:
            if self.ansys.get("_", "ELEM", 0, "ESYM", "MAX") > 0:
                print(
                    "Warning: Elements have non-default csys numbers, ",
                    "but no coordinate systems were provided. ",
                    "Setting all csys numbers to 0...",
                )
                self.ansys.emodif("ALL", "ESYS", 0)
        self.ansys.nummrg("NODE")

        return (self.ansys.mesh.n_node, self.ansys.mesh.n_elem)

    def load_coordinate_systems(self, csysFileAbsolutePath):
        csys_nums, *csys_angles = np.genfromtxt(
            csysFileAbsolutePath, delimiter=",", unpack=True
        )
        with self.ansys.non_interactive:
            for num, angles in zip(csys_nums, zip(*csys_angles)):
                self.ansys.local(num, thxy=angles[0], thyz=angles[1], thzx=angles[2])

        self.ansys.csys()  # Reset to global cartesian

    def get_retained_nodes(self):
        """Get the numbers of the retained nodes in the current mesh.

        Returns:
            list[int]: list of retained node numbers, in order of [N0, N1, N2, N3]
        """
        coord_indices = [
            [(0, 0), (1, 0), (2, 0)],
            [(0, 1), (1, 0), (2, 0)],
            [(0, 0), (1, 1), (2, 0)],
            [(0, 0), (1, 0), (2, 1)],
        ]

        extents = self.mesh_extents()
        node_coords = [[extents[index] for index in node] for node in coord_indices]

        self.retained_nodes = []

        for node in node_coords:
            self.retained_nodes.append(self.get_node_num_at_loc(*node))

        return self.retained_nodes  # for logging purposes

    def get_node_num_at_loc(self, x: float, y: float, z: float) -> int:
        """Get the number of the node at, or closest to, the specifed xyz location.

        WARNING: This uses the Ansys inline node() function, which returns whichever
        node is CLOSEST to the location.

        Args:
            x (float): target x coordinate
            y (float): target y coordinate
            z (float): target z coordinate

        Returns:
            int: number of closest node
        """
        inline = f"node({x},{y},{z})"
        self.ansys.run("NODE_NUMBER_TEMP=" + inline)
        return int(self.ansys.parameters["node_number_temp"])

    def select_node_at_loc(self, x: float, y: float, z: float, kind: str = "S") -> int:
        """Select the node at, or closest to, the specified xyz location.

        Args:
            x (float): target x coordinate
            y (float): target y coordinate
            z (float): target z coordinate
            kind (str, optional): type of selection to be used. Defaults to "S".

        Returns:
            int: number of selected node
        """
        nnum = self.get_node_num_at_loc(x, y, z)
        self.ansys.nsel(kind, "NODE", "", nnum)
        return nnum

    def define_materials(self, materials):
        """Define the material properties in Ansys. Linear isotropic and linear
        orthotropic are currently supported.

        Args:
            materials (list[RecursiveNamespace]): list containing objects holding material data
                Attributes:
                    materialIndex (int): material ID number, minimum of 1
                    materialType (str): material isotropy, "isotropic" or "orthotropic"
                    elasticModuli (list[float]): elastic moduli of material, minimum of 1
                    elasticModuli (list[float]): shear moduli of material, minimum of 1
                    elasticModuli (list[float]): Poisson's ratios of material, minimum of 1
        """
        e_str = ["EX", "EY", "EZ"]
        g_str = ["GXY", "GYZ", "GXZ"]
        pr_str = ["PRXY", "PRYZ", "PRXZ"]

        self.ansys.run("/PREP7")
        for material in materials:
            id = material.materialIndex
            if material.materialType == "isotropic":
                self.ansys.mp("EX", id, material.elasticModuli[0])
                self.ansys.mp("PRXY", id, material.poissonsRatios[0])
            elif material.materialType == "orthotropic":
                for i in range(3):
                    self.ansys.mp(e_str[i], id, material.elasticModuli[i])
                    self.ansys.mp(g_str[i], id, material.shearModuli[i])
                    self.ansys.mp(pr_str[i], id, material.poissonsRatios[i])
        # How do I verify that materials were input correctly? How do I access the
        # materials from self.ansys?
        return

    def solve(self):
        """Calculate the solution for the current load case.
        """
        # with self.ansys.non_interactive:
        self.ansys.run("/SOLU")
        self.ansys.allsel()
        self.ansys.solve()

    def mesh_extents(self, current: bool = False) -> np.ndarray:
        """Calculate +/- xyz extents of mesh.

        Args:
            current (bool, optional): calculate extents of currently selected mesh. Defaults to False.

        Returns:
            np.ndarray: extents formatted as [[-x,+x], [-y,+y], [-z,+z]]
        """
        if not current:
            return np.reshape(self.ansys.mesh.grid.bounds, (-1, 2))
        else:
            mins = self.ansys.mesh.nodes.min(axis=0)
            maxs = self.ansys.mesh.nodes.max(axis=0)
            return np.column_stack((mins, maxs))

    def debug_stat(self):
        self.ansys.lsoper()
        self.ansys.stat()
        self.ansys.fecons()
        self.ansys.stat()
        self.ansys.ceqn()
        self.ansys.stat()

    def generate_base_mesh(
        self, elementType: str, domainSideLength: float, elementSpacing: float, **kwargs
    ):
        """DEPRECATED: Generate uniform cubic mesh according to overall side length and
        element edge length. Assumes a cube centered around (0,0,0).

        Args:
            elementType (str): Ansys element type used to create this mesh
            domainSideLength (float): side length of cubic domain
            elementSpacing (float): target element edge length

        Returns:
            tuple(int, int): tuple containing number of nodes and elements in generated mesh
        """
        half_side = domainSideLength / 2
        self.ansys.run("/PREP7")
        self.ansys.block(
            -half_side, half_side, -half_side, half_side, -half_side, half_side,
        )

        self.ansys.et(1, elementType)
        self.ansys.lesize("ALL", elementSpacing)
        self.ansys.mshkey(1)
        self.ansys.vmesh("ALL")

        assert self.ansys.mesh.n_node > 0, "No nodes generated."
        assert self.ansys.mesh.n_elem > 0, "No elements generated."
        return (self.ansys.mesh.n_node, self.ansys.mesh.n_elem)

    def assign_element_materials(self):
        """DEPRECATED: Assign material numbers to elements located by their centroids.

        This implementation is probably super slow
        Individual emodif commands may be extra slow, so try adding to component
        per material number, then emodif on each component
        """
        self.ansys.run("/PREP7")
        for element in self.test_case.mesh.locationsWithId:
            self.ansys.esel("S", "CENT", "X", element[0])
            self.ansys.esel("R", "CENT", "Y", element[1])
            self.ansys.esel("R", "CENT", "Z", element[2])
            self.ansys.emodif("ALL", "MAT", element[3])

    def load_mesh_with_symlinks(self, nodeFileAbsolutePath, elementFileAbsolutePath):
        temp_path_base = self.jobdir + ".temp_mesh_file"
        try:
            temp_node = Path(temp_path_base + ".node").symlink_to(nodeFileAbsolutePath)
            temp_elem = Path(temp_path_base + ".elem").symlink_to(
                elementFileAbsolutePath
            )
        except OSError as symLinkError:
            print("ERROR: User does not have privileges to create symbolic links.")
            raise symLinkError
        else:
            self.ansys.nread(temp_node)
            self.ansys.eread(temp_elem)
            temp_node.unlink()
            temp_elem.unlink()
