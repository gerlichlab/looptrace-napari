"""Reading looptrace-written, ZARR-stored data"""

from dataclasses import dataclass
from enum import Enum
import logging
from operator import itemgetter
import os
from pathlib import Path
from typing import Dict, Literal, Mapping, Optional, Tuple, Union

import dask.array as da
import numpy as np
import numpy.typing as npt
from numpydoc_decorator import doc
import pandas as pd
from ome_zarr.io import parse_url as parse_zarr_url
from ome_zarr.reader import Reader as ZarrReader

from .geometry import ImagePoint2D
from ._docs import CommonReaderDoc
from ._types import FieldOfViewFrom1, LayerParams, NucleusNumber, PathLike

# Generic ArrayLike since element type differs depending on kind of layer.
FullLayerData = Tuple[npt.ArrayLike, LayerParams, "LayerTypeName"]
# We'll produce one of each of these types of layers.
LayerTypeName = Union[Literal["image"], Literal["labels"], Literal["points"]]

# Specific layer types
ImageLayer = Tuple[npt.ArrayLike, LayerParams, Literal["image"]]
MasksLayer = Tuple[npt.ArrayLike, LayerParams, Literal["labels"]]
CentroidsLayer = Tuple[npt.ArrayLike, LayerParams, Literal["points"]]

# Environment variable for finding nuclei channel if needed.
LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR = "LOOPTRACE_NAPARI_NUCLEI_CHANNEL"


def _read_csv(fp: Path) -> list[Tuple[NucleusNumber, ImagePoint2D]]:
    df = pd.read_csv(fp)
    return [(NucleusNumber(r["label"]), ImagePoint2D(y=r["yc"], x=r["xc"])) for _, r in df.iterrows()]


def _read_zarr(root: Path) -> npt.ArrayLike:
    reader = ZarrReader(parse_zarr_url(root))
    return next(reader()).data


def find_paths_by_fov(folder: Path, *, extension: str) -> Dict[FieldOfViewFrom1, Path]:
    image_paths = {}
    for fn in os.listdir(folder):
        fp = folder / fn
        fov = get_fov_sort_key(fp, extension=extension)
        if fov is not None:
            if fov in image_paths:
                raise Exception(f"FOV {fov} already seen in folder! {folder}")
            image_paths.append((fov, fp))
    return image_paths


class NucleiDataSubfolders(Enum):
    IMAGES = "nuc_images"
    MASKS = "nuc_masks"
    CENTERS = "_nuclear_masks_visualisation"

    @classmethod
    def all_present_within(cls, p: PathLike) -> bool:
        return all(m._is_present_within(p) for m in cls)

    @classmethod
    def read_all_from_root(cls, p: PathLike) -> Dict[FieldOfViewFrom1, "NucleiVisualisationData"]:
        image_paths = find_paths_by_fov(cls.IMAGES.relpath(p), extension=".zarr")
        masks_paths = find_paths_by_fov(cls.MASKS.relpath(p), extension=".zarr")
        centers_paths = find_paths_by_fov(cls.CENTERS.relpath(p), extension=".csv")
        fields_of_view = set(image_paths.keys()) & set(masks_paths.keys()) & set(centers_paths.keys())
        bundles: Dict[FieldOfViewFrom1, "NucleiVisualisationData"] = {}
        for fov in sorted(fields_of_view):
            logging.debug(f"Reading data for FOV: {fov}")
            image_fp: Path = image_paths[fov]
            logging.debug(f"Reading nuclei image: {image_fp}")
            image = _read_zarr(image_fp)
            masks_fp: Path = masks_paths[fov]
            logging.debug(f"Reading nuclei masks: {masks_fp}")
            masks = _read_zarr(masks_fp)
            centers_fp: Path = centers_paths[fov]
            logging.debug(f"Reading nuclei centers: {centers_fp}")
            centers = _read_csv(centers_fp)
            bundles[fov] = NucleiVisualisationData(image=image, masks=masks, centers=centers)
        return bundles

    @classmethod
    def relpaths(cls, p: PathLike) -> Dict[str, Path]:
        return {m.value: m.relpath(p) for m in cls}

    def _is_present_within(self, p: PathLike) -> bool:
        return self.relpath(p).is_dir()

    def relpath(self, p: PathLike) -> Path:
        return Path(p) / self.value
    

def get_fov_sort_key(path: PathLike, *, extension: str) -> Optional[FieldOfViewFrom1]:
    if not isinstance(path, (str, Path)):
        raise TypeError(f"Cannot parse sort-by-FOV key for {extension} stack from alleged path: {path} (type {type(path).__name__})")
    _, fn = os.path.split(path)
    if not fn.startswith("P") or fn.endswith(extension):
        return None
    try:
        rawval = int(fn.lstrip("P").rstrip(extension))
    except TypeError:
        return None
    return FieldOfViewFrom1(rawval)


@doc(
    summary="This is the main hook required by napari / napari plugins to provide a Reader plugin.",
    returns=CommonReaderDoc.returns,
    notes=CommonReaderDoc.returns,
)
def get_reader(path: CommonReaderDoc.path_type):
    def do_not_parse(why: str, *, level: int = logging.DEBUG):
        logging.log(level=level, msg=f"{why}, cannot read looptrace nuclei visualisation data: {path}")
        return None
    
    # Input should be a single extant folder.
    if not isinstance(path, (str, Path)):
        return do_not_parse(f"Not a path-like: {path}")
    if not os.path.isdir(path):
        return do_not_parse(f"Not an extant directory: {path}")
    path: Path = Path(path)
    
    # Each of the subpaths to parse must be extant folder.
    if not NucleiDataSubfolders.all_present_within(path):
        return do_not_parse(
            f"At least one subpath to parse isn't a folder! {NucleiDataSubfolders.relpaths(path)}."
            )

    return lambda root: build_layers(NucleiDataSubfolders.read_all_from_root(root))


@doc(
    summary="Bundle the data needed to visualise nuclei.",
    parameters=dict(
        image="The array of pixel values, e.g. of DAPI staining in a particular FOV",
        masks="""
            The array of region-defining label indicators which represent nuclei regions. 
            The values should be nonnegative integers, with 0 representing portions of the 
            image outside a nucleus, and nonzero values corresponding to a nucleus.
        """,
        centers="The list of centroids, one for each nuclear mask",
    ),
)
@dataclass(frozen=True, kw_only=True)
class NucleiVisualisationData:
    image: npt.ArrayLike
    masks: npt.ArrayLike
    centers: list[Tuple[NucleusNumber, ImagePoint2D]]

    def __post_init__(self) -> None:
        # First, handle the raw image.
        ndim = len(self.image.shape)
        if len(self.image.shape) == 5:
            if self.image.shape[0] != 1:
                raise ValueError(
                    f"5D image for nuclei visualisation must have trivial first dimension; got {self.image.shape[0]} (not 1)"
                    )
            self.image = self.image[0]
        if len(self.image.shape) == 4:
            if self.image.shape[0] == 1:
                self.image = self.image[0]
            else:
                nuc_channel = os.getenv(LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR, "")
                if nuc_channel == "":
                    pass
                try:
                    nuc_channel = int(nuc_channel)
                except TypeError as e:
                    raise ValueError(f"Illegal nuclei channel value (from {LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR}): {nuc_channel}") from e
                if nuc_channel >= self.image.shape[0]:
                    raise ValueError(f"Illegal nuclei channel value (from {LOOPTRACE_NAPARI_NUCLEI_CHANNEL_ENV_VAR}), {nuc_channel}, for channel axis of length {self.image.shape[0]}")
                self.image = self.image[nuc_channel]
        if len(self.image.shape) == 3:
            if self.image.shape[0] == 1:
                self.image = self.image[0]
            else:
                logging.debug("Max projecting along z for nuclei image...")
                self.image = max_project_z(self.img)
        if len(self.image.shape) == 2:
            # All good
            pass
        else:
            raise ValueError("Cannot use image with {ndim} dimension(s) for nuclei visualisation")
        
        # Then, handle the masks image.
        if len(self.masks.shape) == 5:
            if any(d != 1 for d in self.masks.shape[:3]):
                raise ValueError(f"5D nuclear masks image with at least 1 nontrivial (t, c, z) axis! {self.masks.shape}")
            self.masks = self.masks[0, 0, 0]
        if len(self.masks.shape) != 2:
            raise ValueError(f"Need 2D image for nuclear masks! Got {len(self.masks.shape)}: {self.masks.shape}")


def max_project_z(img: npt.ArrayLike) -> npt.ArrayLike:
    if len(img.shape) != 3:
        raise ValueError(f"Image to max-z-project must have 3 dimensions! Got {len(img.shape)}")
    return da.max(img, axis=0)


def build_layers(
    bundles: Mapping[FieldOfViewFrom1, NucleiVisualisationData]
) -> Tuple[ImageLayer, MasksLayer, CentroidsLayer]:
    images = []
    masks = []
    nuclei_points = []
    nuclei_labels = []
    for _, visdata in sorted(bundles.items(), key=itemgetter(0)):
        images.append(visdata.image)
        masks.append(visdata.masks)
        nuc, pt = visdata.centers
        nuclei_points.append([pt.y_coordinate, pt.x_coordinate])
        nuclei_labels.append(nuc)
    images_layer = (da.stack(images, axis=0), {}, "image")
    masks_layer = (da.stack(masks, axis=0), {}, "labels")
    points_layer = (nuclei_points, {"text": "nucleus", "properties": {"nucleus": nuclei_labels}}, "nuclei")
    return images_layer, masks_layer, points_layer
