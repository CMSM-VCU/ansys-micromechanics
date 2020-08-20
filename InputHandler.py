import json
from typing import List
from utils import logger_wraps

import jsonschema
import numpy as np

from TestCase import TestCase
from tuples import Dims, Loads, Material


class InputHandler:
    schema = None
    input_dicts = []

    @logger_wraps()
    def __init__(self, schema_file_path=None):
        if schema_file_path:
            self.load_schema(schema_file_path)
        else:
            print("Creating input handler with no schema...")
        pass

    def load_schema(self, schema_file_path):
        with open(schema_file_path) as schema_file:
            self.schema = json.load(schema_file)

    def check_input_with_schema(self, input_dict, skip_fail=False):
        if self.schema:
            try:
                jsonschema.validate(instance=input_dict, schema=self.schema)
                return True
            except jsonschema.exceptions.ValidationError as err:
                if skip_fail:
                    return False
                else:
                    raise err
        else:
            print("InputHandler: No schema loaded")

    def load_input_files(self, input_file_paths: List, check_first=True):
        for file_path in input_file_paths:
            with open(file_path) as input_file:
                input_dict = json.load(input_file)
                if check_first and self.check_input_with_schema(input_dict):
                    self.input_dicts.append(input_dict)

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
