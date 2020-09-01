from RecursiveNamespace import RecursiveNamespace


class RecursiveClassFactory:
    @staticmethod
    def create_class(name, required_args=(), BaseClass=object):
        arg_filled = [False] * len(required_args)

        def __init__(self, **kwargs):
            for key, _ in kwargs.items():
                try:
                    arg_filled[required_args.index(key)] = True
                except:
                    pass
            if not all(arg_filled):
                raise ValueError("Not all required arguments were filled.")

            for key, value in vars(RecursiveNamespace(**kwargs)).items():
                setattr(self, key, value)

            BaseClass.__init__(self)

        return type(name, (BaseClass,), {"__init__": __init__})
