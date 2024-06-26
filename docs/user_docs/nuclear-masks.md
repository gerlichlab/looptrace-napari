## Viewing nuclear masks
First, check the [general quickstart](./README.md#quickstart), ensuring you have an environment ready to go.

### Quickstart
To visualise the nuclear masks, you need to __drag-and-drop a folder__ into an active Napari window. 
That folder must...
* have `images` as the beginning of its name
<a href="subfolders-structure"></a>
* contain __three subfolders__:
    * `nuc_images`: images (2D), used as input to image segmentation to find nuclei
    * `nuc_masks`: "images" (2D), encoding the subregions of each image deemed to be nuclei. 0 a non-nuclear pixel while positive integer indicates membership of the pixel in a particular nucleus (corresponding to a `label` value in the corresponding points/labels file for the particular field of view in question).
    * `_nuclear_masks_visualisation`: table-like files (CSV), for now, with a `label` column indicating _which_ nucleus a record represents, and `yc` and `xc` columns giving y- and x-coordinates, respectively, for the centroid of a particular nuclear region.

These properties should be nearly satisfied by a run of `looptrace`. 
Perhaps only these steps will be required to prepare the data:
1. Copy the nuclear mask visualisation folder (with the points/labels file(s)) into a shared folder with the nuclei images and masks.
1. Add an underscore as prefix to the name of the copy of the folder.

### What you should see
A Napari window with a single slider (corresponding to field of view) should result, with three layers with names along the lines of "images" or "max_z_projection", "masks", and "labels". 

The fields of view displayed will be those for which all three files (image, masks, and points/labels) were present in the [three subfolders](#subfolders-structure). The `napari` slider is just a 0-based index, so fields of view are relabeled as a contiguous sequence of integers beginning from 0, regardless of how they were initially labeled. This is why it's generally advisable (and how should be done by `looptrace`) to have the same fields of view in each subfolder, numbered as a contiguous subinterval of the natural numbers.

### Details and troubleshooting
* Each relevant file, regardless of which kind of data are inside, should have a basename like `PXXXX`, where `XXXX` corresponds to the 1-based integer index of the field of view, left-padded with zeroes, e.g. P0001.
* Each image or masks file should have a `.zarr` extension.
* Each points/labels file should have a `.nuclear_masks.csv` extension.
* Each `.zarr` should either have a `.zarray` immediately inside it, or have a single `0` subfolder which has a `.zarray` inside it.
* In general, you probably want the fields of view to match up among the three types of files involved (images, masks, points/labels), and to be numbered $1, 2, ..., N$, $N$ being the number of fields of view in your experiment (or whatever subset of the experiment you want to visualise). 
* Each image or masks ZARR should in general be 2D or 5D, each of the first three axes having length 1 if 5D.
* Each points/labels file should have first column unnamed, just as row index; other columns should be `label` (unique per row, natural numbers), then `yc` and `xc` as nonnegative real numbers giving 2D coordinates of nucleus center.

### Frequently asked questions (FAQ)
1. Why __max z projection__?\
    `looptrace` typically does nuclei detection/segmentation in 2D rather than 3D, as in initial testing 3D took substantially more computational time and resources for little gain. Thus, we visualise in 2D what was originally a 3D image (z-stack), and to do so we use max projection in `z` dimension.
