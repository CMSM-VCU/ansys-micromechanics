import os
from pathlib import Path
import time

import numpy as np

from AnsysContainer import AnsysContainer
from utils import logger_wraps

LAUNCH_OPTIONS = {
    "override": True,
    "run_location": os.getcwd() + "\dump_2",
    "jobname": "rve_debug",
    "log_apdl": "w",
}

GEOMETRY = {
    "side_length": 150,
    "fiber_diameter": 15,
    "num_fibers": 45,
    "element_size": 20,
}

FIBERS_OVERRIDE = np.array(
    # [[GEOMETRY["side_length"] / 2, GEOMETRY["side_length"] / 2]]
    [
        [0, 0],
        [GEOMETRY["side_length"], 0],
        [GEOMETRY["side_length"], GEOMETRY["side_length"]],
        [0, GEOMETRY["side_length"]],
    ]
)

X0 = 0.0
X1 = GEOMETRY["side_length"]
Y0 = 0.0
Y1 = GEOMETRY["side_length"]

np.random.seed(0)


@logger_wraps()
def main(side_length, fiber_diameter, num_fibers, element_size):
    if FIBERS_OVERRIDE is None:
        fibers, fibers_copy = generate_fiber_centroids(**GEOMETRY)
    else:
        fibers_copy = FIBERS_OVERRIDE

    with AnsysContainer(LAUNCH_OPTIONS) as ansys:
        ansys.finish()
        ansys.run("/clear")
        ansys.run("/prep7")

        ansys.blc4(0, 0, side_length, side_length)

        with ansys.non_interactive:
            for cent in fibers_copy:
                ansys.cyl4(cent[0], cent[1], fiber_diameter / 2)

        ansys.aovlap("all")

        with ansys.non_interactive:
            ansys.lsel("S", "LOC", "X", X0, X1)
            ansys.lsel("R", "LOC", "Y", Y0, Y1)
            ansys.lsel("INVE")
            ansys.asll()
        ansys.adele("ALL", "", "", 1)
        ansys.allsel()
        ansys.aglue("ALL")

        with ansys.non_interactive:
            ansys.et(1, 186)
            ansys.et(2, 183, 1)

            ansys.lsel("S", "LOC", "X", X1)
            ansys.lsel("A", "LOC", "X", X0)
            ansys.lsel("A", "LOC", "Y", Y1)
            ansys.lsel("A", "LOC", "Y", Y0)
            ansys.lesize("ALL", side_length / element_size)
            ansys.esize(side_length / element_size)
            ansys.smrtsize(4)
            ansys.allsel()

        max_anum = ansys.geometry.anum.max()
        with ansys.non_interactive:  # ansys.geometry not available inside non_interactive?
            ansys.asel("S", "AREA", "", max_anum)
            ansys.asel("INVE")
            ansys.aatt("2")
            ansys.allsel()

        ansys.amesh("ALL")

        ansys.extopt("ESIZE", element_size)
        ansys.extopt("ACLEAR", 1)
        ansys.extopt("ATTR", 1)

        ansys.numcmp("all")
        anum = list(ansys.geometry.anum)
        ansys.vext("ALL", "", "", dx="", dy="", dz=side_length)

        ansys.run("/PREP7")
        ansys.nummrg("ALL")
        ansys.numcmp("ALL")

        # ansys.et(3, 185)
        # ansys.emodif("ALL", "TYPE", 3)
        # ansys.et(1, 185)
        # ansys.emodif("ALL", "TYPE", 1)
        # ansys.nsle("S")
        # ansys.nsel("INVE")
        # ansys.ndele("ALL")    # Can't delete the former midside nodes?

        # Align composite 1-2-3 axes with global x-y-z axes
        ansys.wprota(thxy=90, thyz=90)
        ansys.vtran(kcnto=4, nv1="ALL", noelem=0, imove=1)

        ansys.open_gui()

        save_path = str(Path.cwd() / "examples/fiber_ex03")
        ansys.nwrite(save_path + ".node")
        ansys.ewrite(save_path + ".elem")

        pass


def generate_fiber_centroids(side_length, fiber_diameter, num_fibers, **kwargs):
    min_coord, coord_range = get_bounds(side_length, fiber_diameter)
    # init_rand = np.random.rand(num_fibers, 2)

    # centroids_try = min_coord + (init_rand * coord_range)

    offsets = [[0, 1], [0, -1], [1, 1], [1, 0], [1, -1], [-1, 1], [-1, 0], [-1, -1]]

    fibers = None
    fibers_copy = None
    fibers_down = 0
    tries = 0
    while fibers_down < num_fibers:
        tries += 1
        fiber_try = (np.random.rand(1, 2) * side_length) + X0
        if fibers_down == 0:
            fibers = np.array(fiber_try).reshape((1, 2))
            fibers_down += 1
            fibers_copy = np.vstack(
                [
                    fibers,
                    *[offset_xy(fiber_try, offset, side_length) for offset in offsets],
                ]
            )
            continue
        else:

            diff = fibers_copy - fiber_try
            dist_sq = (diff[:, 0] ** 2) + (diff[:, 1] ** 2)
            if np.any(dist_sq <= (fiber_diameter) ** 2 * 1.05):
                continue

            edge_dist = np.abs(np.abs(fiber_try - (X1 - X0) / 2) - side_length / 2)
            if np.any(
                np.logical_and(
                    edge_dist <= (fiber_diameter / 2) * 1.15,
                    edge_dist >= (fiber_diameter / 2) * 0.75,
                )
            ):
                # print(edge_dist)
                continue

            fibers = np.vstack([fibers, fiber_try])
            fibers_down += 1
            fibers_copy = np.vstack(
                [
                    fibers_copy,
                    fiber_try,
                    *[offset_xy(fiber_try, offset, side_length) for offset in offsets],
                ]
            )
            print(fibers_down, " ", end="")
    print(tries)
    return fibers, fibers_copy


def get_bounds(side_length, fiber_diameter):
    return -side_length / 2.0, side_length


def offset_xy(coords, mult, mag):
    return coords + (np.array(mult) * mag)


if __name__ == "__main__":
    main(**GEOMETRY)
