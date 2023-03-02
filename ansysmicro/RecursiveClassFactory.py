from typing import Sequence, Type

from .RecursiveNamespace import RecursiveNamespace


class RecursiveClassFactory:
    @staticmethod
    def create_class(
        name: str, required_args: Sequence[str] = (), BaseClass: Type = object
    ) -> Type:
        """Create a subclass with required constructor arguments defined at runtime

        Args:
            name (str): name of subclass to be created
            required_args (Sequence[str], optional): names of required arguments. Defaults to ().
            BaseClass (Type, optional): base class of created subclass. Defaults to object.

        Raises:
            ValueError: raised by subclass constructor if required arguments are not filled

        Returns:
            Type: subclass with modified constructor
        """
        arg_filled = [False] * len(required_args)

        def __init__(self, **kwargs):
            for key, _ in kwargs.items():
                try:
                    arg_filled[required_args.index(key)] = True
                except ValueError:
                    # Extra arguments are okay, but raise ValueError with .index()
                    pass
            if not all(arg_filled):
                raise ValueError("Not all required arguments were filled.")

            # vars(RN(**dict)).items() includes all methods, not just dict contents
            for key, value in vars(RecursiveNamespace(**kwargs)).items():
                setattr(self, key, value)

            BaseClass.__init__(self)

        def __repr__(self):
            return "\n".join(
                [f"{key}: {var.__repr__()}" for key, var in vars(self).items()]
            )

        return type(name, (BaseClass,), {"__init__": __init__, "__repr__": __repr__})
