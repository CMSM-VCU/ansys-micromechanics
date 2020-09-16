import json
import pathlib
from typing import List

import jsonschema
import numpy as np

from utils import logger_wraps, decorate_all_methods


@decorate_all_methods(logger_wraps)
class InputHandler:
    schema = None
    input_dicts = []

    def __init__(self, schema_file_path=None):
        if schema_file_path:
            self.load_schema(schema_file_path)
        else:
            print("Creating input handler with no schema...")
        pass

    def load_schema(self, schema_file_path):
        with open(schema_file_path) as schema_file:
            self.schema = json.load(schema_file)

        if self.schema:
            return True
        else:
            print("InputHandler: Schema load failed")
            return False

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
            return False

    def load_input_files(self, input_file_paths: List, check_first=True):
        for file_path in input_file_paths:
            with open(file_path) as input_file:
                input_dict = json.load(input_file)
                input_dict["path"] = pathlib.Path(file_path).resolve(strict=True)
                if check_first and self.check_input_with_schema(input_dict):
                    self.input_dicts.append(input_dict)
        return len(self.input_dicts)

    def get_required_properties(self):
        # TODO: Make this recursive to get required properties of properties
        # How to do required properties of optional properties though?
        if self.schema:
            return self.schema["required"]
        else:
            print("InputHandler: No schema loaded")
            return False
