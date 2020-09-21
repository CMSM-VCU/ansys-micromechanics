# Taken from https://dev.to/taqkarim/extending-simplenamespace-for-nested-dictionaries-58e8
class RecursiveNamespace:
    @staticmethod
    def map_entry(entry):
        if isinstance(entry, dict):
            return RecursiveNamespace(**entry)
        return entry

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            if type(val) == dict:
                setattr(self, key, RecursiveNamespace(**val))
            elif type(val) == list:
                setattr(self, key, list(map(self.map_entry, val)))
            else:  # this is the only addition
                setattr(self, key, val)

    def __repr__(self):
        return (
            "\n\t"
            + "\n\t".join(
                [f"{key}: {var.__repr__()}" for key, var in vars(self).items()]
            )
            + "\n"
        )

    def keys(self):
        return vars(self).keys()

    def __getitem__(self, key):
        return getattr(self, key)
