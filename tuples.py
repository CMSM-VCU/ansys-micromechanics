from collections import namedtuple

Dims = namedtuple("Dims", ["side_length", "element_length"])
Material = namedtuple(
    "Material", ["id", "elastic_moduli", "shear_moduli", "poisson_ratios"]
)
Loads = namedtuple("Loads", ["kind", "normal_magnitude", "shear_magnitude"])
