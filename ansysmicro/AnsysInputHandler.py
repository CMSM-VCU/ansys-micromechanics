from .InputHandler import InputHandler
from .RecursiveClassFactory import RecursiveClassFactory
from .TestCaseSkeleton import TestCaseSkeleton
from .utils import decorate_all_methods, logger_wraps


@decorate_all_methods(logger_wraps)
class AnsysInputHandler(InputHandler):
    def create_testcase_class(self):
        return RecursiveClassFactory.create_class(
            "AnsysTestCase",
            required_args=self.get_required_properties + ["path"],
            BaseClass=TestCaseSkeleton,
        )
