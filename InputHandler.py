import json
import pathlib
from typing import List

import jsonschema

from utils import decorate_all_methods, logger_wraps


@decorate_all_methods(logger_wraps)
class InputHandler:
    schema = None
    input_dicts = []

    def __init__(self, schema_file_path: str = None):
        if schema_file_path:
            self.schema = InputHandler.load_schema(schema_file_path)
        else:
            print("Creating input handler with no schema...")
        pass

    @staticmethod
    def load_schema(schema_file_path: str) -> dict:
        with open(schema_file_path) as schema_file:
            schema = json.load(schema_file)

        assert schema, "Failed to load schema."
        return schema

    @staticmethod
    def check_dict_against_schema(
        input_dict: dict, schema: dict, raise_failure: bool = True
    ) -> bool:
        try:
            jsonschema.validate(instance=input_dict, schema=schema)
            return True
        except jsonschema.exceptions.ValidationError as err:
            if raise_failure:
                raise err
            else:
                return False

    def check_input(self, input_dict: dict, raise_failure: bool = True):
        if self.schema:
            return InputHandler.check_dict_against_schema(
                input_dict, self.schema, raise_failure
            )
        else:
            print("InputHandler: No schema loaded")
            return False

    def load_input_files(
        self, input_file_paths: List[str], check_first: bool = True
    ) -> int:
        for file_path in input_file_paths:
            with open(file_path) as input_file:
                input_dict = json.load(input_file)
                input_dict["path"] = pathlib.Path(file_path).resolve(strict=True)
                if check_first and self.check_input(input_dict, raise_failure=True):
                    self.input_dicts.append(input_dict)
                elif not check_first:
                    self.input_dicts.append(input_dict)

        return len(self.input_dicts)

    @property
    def get_required_properties(self) -> List[str]:
        # TODO: Make this recursive to get required properties of properties
        # How to do required properties of optional properties though?
        if self.schema:
            return self.schema["required"]
        else:
            print("InputHandler: No schema loaded")
            return False
