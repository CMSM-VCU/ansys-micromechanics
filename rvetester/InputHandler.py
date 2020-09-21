import json
import pathlib
from typing import List

import jsonschema

from .utils import decorate_all_methods, logger_wraps


@decorate_all_methods(logger_wraps)
class InputHandler:
    """Handler for loading, parsing, and validating input files against a specification.
    Input files use the JSON format, and are validated using the JSON schema standard.

    Note: Input files may not contain the top-level property "path", which is
    automatically set in load_input_files().
    """

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
        """Load JSON schema from file. Currently, this is functionally identical to
        loading any other JSON file. This method exists to allow for future
        implementation of processing of the schema.

        Args:
            schema_file_path (str): Absolute or relative path to JSON schema file.

        Returns:
            dict: JSON schema, stored as dict
        """
        with open(schema_file_path) as schema_file:
            schema = json.load(schema_file)

        assert schema, "Failed to load schema."
        return schema

    @staticmethod
    def validate_dict_against_schema(
        input_dict: dict, schema: dict, raise_failure: bool = True
    ) -> bool:
        """Validate the given dict object against a JSON schema, stored as its own dict.
        By default, raises error if validation fails, but can instead be set to return
        False on failed validation.

        Args:
            input_dict (dict): dict object to be validated
            schema (dict): dict containing JSON schema to be validated against
            raise_failure (bool, optional): Whether to raise an error on failed
                Validation. Defaults to True.

        Raises:
            err: input_dict failed validation against schema.

        Returns:
            bool: Whether input_dict succeeded validation.
        """
        try:
            jsonschema.validate(instance=input_dict, schema=schema)
            return True
        except jsonschema.exceptions.ValidationError as err:
            if raise_failure:
                raise err
            else:
                return False

    def check_input(self, input_dict: dict, raise_failure: bool = True) -> bool:
        """Calls validate_dict_against_schema and passes self.schema as the schema
        argument. Returns False if this InputHandler instance has no schema loaded.

        Args:
            input_dict (dict): dict object to be checked (validated).
            raise_failure (bool, optional): Whether to raise an error on failed check.
                Defaults to True.

        Returns:
            bool: Whether input_dict succeeded validation.
        """
        if self.schema:
            return InputHandler.validate_dict_against_schema(
                input_dict, self.schema, raise_failure
            )
        else:
            print("InputHandler: No schema loaded")
            return False

    def load_input_files(
        self, input_file_paths: List[str], check_first: bool = True
    ) -> int:
        """Load, parse, and check a series of input files from a list of paths. Input
        files must be in JSON format and are loaded using json.load(). Checking
        (against a JSON schema) can be disabled.

        Loaded input files are stored as dicts in this InputHandler instance's
        input_dicts attribute.

        The absolute path to the input file is added to the resulting dictionary, under
        the key "path".

        Args:
            input_file_paths (List[str]): List of absolute or relative paths to input
                files.
            check_first (bool, optional): Whether to check the input file against the
                JSON schema before keeping. Defaults to True.

        Returns:
            int: Number of successfully loaded input files.
        """
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
        """Get list of required properties from this InputHandler's schema.
        Note: This currently only accesses the top level of required properties. This
        provides no information on required properties of properties, etc.

        TODO: Make this recursive to get required properties of properties
        How to do required properties of optional properties though?

        Returns:
            List: List of names of top-level required properties.
        """
        if self.schema:
            return self.schema["required"]
        else:
            print("InputHandler: No schema loaded")
            return False
