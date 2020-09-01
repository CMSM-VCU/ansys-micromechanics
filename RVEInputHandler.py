from InputHandler import InputHandler
from RecursiveClassFactory import RecursiveClassFactory
from TestCaseSkeleton import TestCaseSkeleton
from utils import decorate_all_methods, logger_wraps


@decorate_all_methods(logger_wraps)
class RVEInputHandler(InputHandler):
    def create_testcase_class(self):
        return RecursiveClassFactory.create_class(
            "RVETestCase",
            required_args=self.get_required_properties(),
            BaseClass=TestCaseSkeleton,
        )
