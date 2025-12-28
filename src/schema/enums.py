from enum import Enum


class ProcessingStatus(str, Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


class FrameGeometry(str, Enum):
    rectangular = "rectangular"
    round = "round"
    oval = "oval"
    aviator = "aviator"
    cat_eye = "cat-eye"
    geometric = "geometric"
    irregular = "irregular"
    unknown = "unknown"


class Transparency(str, Enum):
    opaque = "opaque"
    semi_transparent = "semi-transparent"
    transparent = "transparent"
    mixed = "mixed"


class SurfaceTexture(str, Enum):
    smooth = "smooth"
    matte = "matte"
    glossy = "glossy"
    textured = "textured"
    patterned = "patterned"
    metallic = "metallic"


class FrameMaterialApparent(str, Enum):
    metal = "metal"
    plastic = "plastic"
    acetate = "acetate"
    titanium = "titanium"
    wood = "wood"
    mixed = "mixed"
    indeterminate = "indeterminate"


class LensTint(str, Enum):
    clear = "clear"
    tinted = "tinted"
    gradient = "gradient"
    mirrored = "mirrored"
    photochromic = "photochromic"
    gray = "gray"
    brown = "brown"
    green = "green"
    blue = "blue"
    indeterminate = "indeterminate"


class TempleStyle(str, Enum):
    standard = "standard"
    spring_hinge = "spring-hinge"
    cable = "cable"
    skull = "skull"
    indeterminate = "indeterminate"
