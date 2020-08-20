import numpy as np

from InputHandler import InputHandler
from TestCase import TestCase
from tuples import Dims, Loads, Material


class RVEInputHandler(InputHandler):
    def convert_input_dict_to_testcase(self, input_dict):
        # throw warning if side length and element length are not divisible

        dict_dims = input_dict["dimensions"]
        dict_mats = input_dict["materials"]
        dict_loads = input_dict["loading"]

        dims = Dims(dict_dims["domainSideLength"], dict_dims["elementSpacing"],)
        materials = [
            Material(
                mat["materialIndex"],
                mat["elasticModuli"],
                mat["shearModuli"],
                mat["poissonsRatios"],
            )
            for mat in dict_mats
        ]
        loads = Loads(
            dict_loads["kind"],
            dict_loads["normalMagnitude"],
            dict_loads["shearMagnitude"],
        )
        arrangement = np.array(input_dict["materialLocations"]["locationsWithId"])

        return TestCase(dims, materials, arrangement, loads)
